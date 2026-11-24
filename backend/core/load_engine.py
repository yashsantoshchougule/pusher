"""
Async Load Engine for Pusher Load Testing Platform.
- httpx.AsyncClient with connection pooling bounded by 70% OS File-Descriptor cap
- 4 KB chunk-discard streaming worker (aiter_bytes(4096) immediately discarded)
- 3 Traffic Modes: Step-Ramp (5 equal steps), Sudden Rush (3s warmup), Steady Crowd (instant 100%)
- Dynamic Cache-Busting (?_cb=nonce)
- Live 1s rolling telemetry and Safety Circuit Breakers (error %, p95 latency, RSS RAM)
"""

import asyncio
from array import array
import collections
import math
import os
from uuid import uuid4
import sys
import time
from time import monotonic_ns
import urllib.parse
import httpx
import psutil
from starlette.websockets import WebSocket

from backend.core.circuit_breakers import CircuitBreakers
from backend.core.journey_service import (
    JourneyInputError, append_cache_buster, build_journey_request, extract_journey_value, journey_request_headers,
)
from backend.core.request_owner import request_owner
from backend.core.target_policy import DestinationError, parse_target, target_client

# Locked Pusher Invariants
BASE_ENGINE_RAM_MB = 50
RAM_PER_VU_MB = 0.20
DEFAULT_RAM_CEILING_MB = 500
MAX_REQUESTED_VUS = 100_000
CHUNK_SIZE_BYTES = 4096  # 4 KB chunk discard
LATENCY_OVERFLOW_MS = 60_001
STEP_RAMP_RATIOS = (0.20, 0.40, 0.60, 0.80, 1.00)
STEP_RAMP_MIN_SECONDS = 1.0
RUSH_WARMUP_SECONDS = 3.0
RUSH_WARMUP_RATIO = 0.10
RUSH_WARMUP_MIN_VUS = 10


class ConnectionManager:
    """Manages active client WebSocket connections for real-time telemetry streaming."""
    def __init__(self):
        self.active_connections: dict[WebSocket, str] = {}

    def register(self, websocket: WebSocket, owner_id: str):
        self.active_connections[websocket] = owner_id

    def disconnect(self, websocket: WebSocket):
        self.active_connections.pop(websocket, None)

    async def broadcast(self, data: dict, owner_id: str | None = None):
        async def send(connection):
            try:
                await asyncio.wait_for(connection.send_json(data), timeout=0.05)
            except Exception:
                self.disconnect(connection)
        await asyncio.gather(*(send(connection) for connection, recipient in self.active_connections.items()
                               if recipient == owner_id))


def calculate_max_allowed_vus(ram_limit_mb: int) -> int:
    """Calculate maximum concurrent VUs allowed under the given RAM ceiling."""
    if ram_limit_mb <= BASE_ENGINE_RAM_MB:
        return 0
    return math.floor((ram_limit_mb - BASE_ENGINE_RAM_MB) / RAM_PER_VU_MB)


def calculate_active_vus(traffic_mode: str, target_vus: int, duration_sec: int, elapsed: float) -> int:
    """
    Calculate desired concurrency at a given elapsed time according to traffic mode:
    - Step-Ramp: 5 equal steps (20%, 40%, 60%, 80%, 100%)
    - Sudden Rush: 3s warmup at 10% (min 10), then instant 100% surge
    - Steady Crowd: Constant 100% concurrency
    """
    if target_vus <= 0:
        return 0

    mode = traffic_mode.lower().replace("-", "_").replace(" ", "_")

    if mode == "step_ramp":
        step_len = max(STEP_RAMP_MIN_SECONDS, duration_sec / len(STEP_RAMP_RATIOS))
        step_index = min(len(STEP_RAMP_RATIOS) - 1, int(elapsed // step_len))
        ratio = STEP_RAMP_RATIOS[step_index]
        return max(1, int(round(target_vus * ratio)))

    elif mode == "sudden_rush":
        if elapsed < RUSH_WARMUP_SECONDS:
            warmup = min(target_vus, max(RUSH_WARMUP_MIN_VUS, round(target_vus * RUSH_WARMUP_RATIO)))
            return warmup
        return target_vus

    else:  # Default / steady_crowd
        return target_vus


def get_os_fd_cap() -> int:
    """Determine the 70% OS File-Descriptor concurrency limit."""
    try:
        if sys.platform != "win32":
            import resource
            soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
            return int(soft_limit * 0.70)
        else:
            # Windows typical standard socket handle safety cap
            return int(4096 * 0.70)
    except Exception:
        return 1024


class LoadEngine:
    def __init__(self):
        self.owner_id: str | None = None
        self.is_running: bool = False
        self.run_id: str | None = None
        self._status_revision = 0
        self.start_time: float = 0.0
        self.duration_sec: int = 0
        self.target_vus: int = 0
        self._worker_limit = 0
        self.traffic_mode: str = "steady_crowd"
        self.target_url: str = ""
        self.is_sandbox: bool = False
        self.cache_bust: bool = True
        self.active_guard_id: str = ""
        self.guard_expires_at: float | None = None
        self.ram_limit_mb: int = DEFAULT_RAM_CEILING_MB
        self.max_error_pct: float = 15.0
        self.p95_ceiling_ms: float = 1500.0
        self.request_timeout_sec = 5.0
        self.brakes = CircuitBreakers(self.max_error_pct, self.p95_ceiling_ms)
        self.circuit_status: str = "ARMED (Normal)"

        self.use_journey: bool = False
        self.journey_steps: list[dict] = []
        self.step_metrics: list[dict] = []
        self.timeseries_buckets: list[dict] = []
        self._sample_interval = 1
        self._peak_rps = 0
        self._request_vus = 0
        self._peak_vus = 0

        self.connection_manager = ConnectionManager()
        self._stop_event = asyncio.Event()
        self._master_task: asyncio.Task | None = None
        self._worker_tasks: list[asyncio.Task] = []

        # Metrics accumulators
        self.total_requests: int = 0
        self.status_2xx: int = 0
        self.status_429: int = 0
        self.status_5xx: int = 0
        self.status_other: int = 0
        self.bytes_discarded: int = 0
        self._failed_requests = 0
        self._successful_journeys = 0
        self._latency_counts = array("Q", [0]) * (LATENCY_OVERFLOW_MS + 1)
        self._max_latency_ms = 0.0

        # Rolling 1-second window deques: (timestamp, latency_ms), (timestamp, is_error, bytes)
        self._rolling_latencies = collections.deque()
        self._rolling_requests = collections.deque()


    def get_status(self, owner_id: str | None = None) -> dict:
        self._status_revision = max(self._status_revision + 1, monotonic_ns() // 1000)
        if owner_id is not None and owner_id != self.owner_id:
            return {"is_running": False, "run_id": None, "status_revision": self._status_revision,
                    "elapsed_sec": 0, "active_vus": 0, "live_rps": 0,
                    "p95_ms": 0, "error_pct": 0, "use_journey": False,
                    "step_metrics": [], "circuit_status": "ARMED (Normal)"}
        now = time.time()
        elapsed = int(now - self.start_time) if self.is_running else 0

        # Prune rolling windows older than 1.0 second
        while self._rolling_latencies and now - self._rolling_latencies[0][0] > 1.0:
            self._rolling_latencies.popleft()
        while self._rolling_requests and now - self._rolling_requests[0][0] > 1.0:
            self._rolling_requests.popleft()

        live_rps = len(self._rolling_requests)
        
        # Calculate p95 latency from rolling window
        if self._rolling_latencies:
            sorted_latencies = sorted(lat for _, lat in self._rolling_latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p95_ms = round(sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)], 1)
        else:
            p95_ms = 0.0

        # Calculate error percentage from rolling window
        if self._rolling_requests:
            error_count = sum(1 for _, is_err, _ in self._rolling_requests if is_err)
            error_pct = round((error_count / len(self._rolling_requests)) * 100.0, 1)
        else:
            error_pct = 0.0

        # Current active VUs according to scheduler
        active_vus = (
            min(self._worker_limit, calculate_active_vus(self.traffic_mode, self.target_vus, self.duration_sec, elapsed))
            if self.is_running
            else 0
        )

        # Process RSS Memory
        try:
            ram_mb = round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1)
        except Exception:
            ram_mb = 52.0

        return {
            "is_running": self.is_running,
            "run_id": self.run_id,
            "status_revision": self._status_revision,
            "elapsed_sec": min(elapsed, self.duration_sec),
            "duration_sec": self.duration_sec,
            "traffic_mode": self.traffic_mode,
            "active_vus": active_vus,
            "target_vus": self.target_vus,
            "live_rps": live_rps,
            "p95_ms": p95_ms,
            "error_pct": error_pct,
            "total_requests": self.total_requests,
            "status_2xx": self.status_2xx,
            "status_429": self.status_429,
            "status_5xx": self.status_5xx,
            "bytes_discarded_mb": round(self.bytes_discarded / (1024 * 1024), 2),
            "ram_mb": ram_mb,
            "ram_limit_mb": self.ram_limit_mb,
            "circuit_status": self.circuit_status,
            "use_journey": self.use_journey,
            "step_metrics": self.step_metrics,
        }

    async def start(
        self,
        target_url: str,
        traffic_mode: str,
        target_vus: int,
        duration_sec: int,
        cache_bust: bool = True,
        active_guard_id: str = "PG-ACTIVE",
        ram_limit_mb: int = DEFAULT_RAM_CEILING_MB,
        max_error_pct: float = 15.0,
        p95_ceiling_ms: float = 1500.0,
        use_journey: bool = False,
        journey_steps: list[dict] | None = None,
        is_sandbox: bool = False,
        request_timeout_sec: float = 5.0,
        guard_expires_at: float | None = None,
    ) -> str:
        if self.is_running or (self._master_task and not self._master_task.done()):
            raise RuntimeError("A load test is already actively running.")

        owner_id = request_owner.get()
        self.owner_id = owner_id
        self.is_sandbox = is_sandbox
        self.target_url = str(parse_target(target_url))

        self.traffic_mode = traffic_mode
        self.target_vus = target_vus
        self._worker_limit = max(1, min(target_vus, get_os_fd_cap()))
        self.duration_sec = duration_sec
        self.cache_bust = cache_bust
        self.active_guard_id = active_guard_id
        self.guard_expires_at = guard_expires_at
        self.ram_limit_mb = ram_limit_mb
        self.max_error_pct = max_error_pct
        self.p95_ceiling_ms = p95_ceiling_ms
        self.request_timeout_sec = request_timeout_sec
        self.brakes = CircuitBreakers(max_error_pct, p95_ceiling_ms)
        self.circuit_status = "ARMED (Normal)"

        self.use_journey = use_journey
        if use_journey:
            if journey_steps:
                self.journey_steps = journey_steps
            else:
                from backend.core.journey_service import journey_store
                self.journey_steps = journey_store.steps

            self.step_metrics = [
                {
                    "step_id": s.get("step_id", idx + 1),
                    "name": s.get("name", f"Step {idx + 1}"),
                    "method": s.get("method", "GET").upper(),
                    "path": s.get("path", "").partition("?")[0],
                    "requests": 0,
                    "passed": 0,
                    "failed": 0,
                    "avg_latency_ms": 0.0,
                    "last_status": 0,
                }
                for idx, s in enumerate(self.journey_steps)
            ]
        else:
            self.journey_steps = []
            self.step_metrics = []

        self.run_id = f"RUN-{uuid4().hex}"
        self.start_time = time.time()
        self.is_running = True

        self._stop_event = asyncio.Event()
        self.total_requests = 0
        self.status_2xx = 0
        self.status_429 = 0
        self.status_5xx = 0
        self.status_other = 0
        self.bytes_discarded = 0
        self._failed_requests = 0
        self._successful_journeys = 0
        self._latency_counts = array("Q", [0]) * (LATENCY_OVERFLOW_MS + 1)
        self._max_latency_ms = 0.0
        self._rolling_latencies.clear()
        self._rolling_requests.clear()
        self.timeseries_buckets = []
        self._sample_interval = max(1, math.ceil(duration_sec / 3600))
        self._peak_rps = 0
        self._request_vus = 0
        self._peak_vus = 0

        # Start master orchestrator task
        self._master_task = asyncio.create_task(self._run_orchestrator())
        try:
            asyncio.create_task(self.broadcast_telemetry(event="START"))
        except RuntimeError:
            pass
        return self.run_id

    async def broadcast_telemetry(self, event: str = "TICK"):
        """Broadcast live telemetry frame to all active WebSocket clients."""
        status = self.get_status()
        status["event"] = event
        await self.connection_manager.broadcast(status, self.owner_id)

    def request_stop(self, status: str):
        if self.is_running and not self._stop_event.is_set():
            self.circuit_status = status
            self._stop_event.set()

    async def stop(self, reason: str = "MANUAL_ABORT"):
        self.request_stop(f"STOPPED ({reason})")
        if self._master_task is not None:
            await asyncio.shield(self._master_task)

    async def simulate_spike(self) -> dict:
        """
        Exercise the circuit breaker's stop path without counting simulated responses.
        """
        if not self.is_running:
            raise RuntimeError("No active load test is running to inject faults.")

        self.request_stop("TRIPPED (Simulated 429/5xx spike)")
        await asyncio.shield(self._master_task)

        return {
            "status": "tripped",
            "circuit_status": self.circuit_status,
            "run_id": self.run_id,
        }

    async def _run_orchestrator(self):
        timeout = httpx.Timeout(self.request_timeout_sec)
        try:
            async with target_client(
                parse_target(self.target_url), self.is_sandbox, timeout=timeout, connections=self._worker_limit
            ) as client:
                if not self._stop_event.is_set():
                    worker = self._vu_journey_worker if self.use_journey and self.journey_steps else self._vu_worker
                    self._worker_tasks = [asyncio.create_task(worker(client, i)) for i in range(self._worker_limit)]
                    for task in self._worker_tasks:
                        task.add_done_callback(self._worker_finished)
                    monitor = asyncio.create_task(self._circuit_monitor())
                    try:
                        await self._monitor_until_stopped()
                    finally:
                        self._stop_event.set()
                        tasks = [monitor, *self._worker_tasks]
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                        self._worker_tasks = []
        except asyncio.CancelledError:
            self.circuit_status = "STOPPED (ENGINE_SHUTDOWN)"
            raise
        except Exception:
            self.circuit_status = "STOPPED (ENGINE_FAILURE)"
            raise
        finally:
            self.is_running = False
            await self._finish_run()

    def _worker_finished(self, task: asyncio.Task):
        if not task.cancelled() and task.exception() is not None:
            self.request_stop("FAILED (Worker error)")

    async def _monitor_until_stopped(self):
        last_tick = time.monotonic()
        while not self._stop_event.is_set():
            wall_time = time.time()
            guard_remaining = self._guard_remaining(wall_time)
            if guard_remaining <= 0:
                self.request_stop("TRIPPED (Guard verification expired)")
                break
            elapsed = wall_time - self.start_time
            remaining = self.duration_sec - elapsed
            if remaining <= 0:
                break
            now = time.monotonic()
            if now - last_tick >= 1:
                last_tick = now
                snapshot = self.get_status()
                self._sample_run(elapsed, snapshot)
                await self.broadcast_telemetry(event="TICK")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=min(remaining, guard_remaining, 0.1))
            except TimeoutError:
                pass

    def _sample_run(self, elapsed, snapshot):
        self._peak_rps = max(self._peak_rps, snapshot["live_rps"])
        slot = int(elapsed) // self._sample_interval
        point = {
            "elapsed_sec": int(elapsed), "vus": snapshot["active_vus"],
            "rps": snapshot["live_rps"], "p95_ms": snapshot["p95_ms"],
            "error_pct": snapshot["error_pct"],
        }
        if self.timeseries_buckets and self.timeseries_buckets[-1]["elapsed_sec"] // self._sample_interval == slot:
            self.timeseries_buckets[-1] = point
        elif len(self.timeseries_buckets) < 3600:
            self.timeseries_buckets.append(point)

    async def _finish_run(self):
        # Archive completed run if not already recorded
        final_status = self.circuit_status
        if "STOPPED" in final_status:
            verdict_cat = "MANUAL_ABORT"
            display_status = f"MANUAL ABORT ({final_status})"
            event_type = "STOP"
        elif "TRIPPED" in final_status:
            verdict_cat = "CIRCUIT_BREAKER"
            display_status = f"CIRCUIT BREAKER ({final_status})"
            event_type = "CIRCUIT_TRIPPED"
        elif final_status.startswith("FAILED"):
            verdict_cat = "FAILED"
            display_status = final_status
            event_type = "STOP"
        elif self.total_requests == self._failed_requests:
            verdict_cat = "FAILED"
            display_status = (
                "FAILED (No successful requests)" if self.total_requests else "FAILED (No requests completed)"
            )
            event_type = "COMPLETE"
        elif self.use_journey and self._successful_journeys == 0:
            verdict_cat = "FAILED"
            display_status = "FAILED (No successful journeys)"
            event_type = "COMPLETE"
        else:
            verdict_cat = "PASSED"
            display_status = f"PASSED (Completed {self.duration_sec}s)"
            event_type = "COMPLETE"

        now_str = time.strftime("%H:%M:%S")
        status_snap = self.get_status()
        elapsed_actual = min(int(time.time() - self.start_time), self.duration_sec)

        from backend.core.report_service import detect_knee_of_curve, save_run
        knee_analysis = detect_knee_of_curve(self.timeseries_buckets, self.target_vus, self.p95_ceiling_ms)

        peak_rps_val = max(self._peak_rps, status_snap["live_rps"])

        sqlite_record = {
            "run_id": self.run_id,
            "timestamp": now_str,
            "target_url": self.target_url,
            "guard_id": self.active_guard_id,
            "mode": self.traffic_mode.replace("_", " ").title(),
            "target_vus": self.target_vus,
            "peak_vus": self._peak_vus,
            "duration_sec": self.duration_sec,
            "elapsed_sec": elapsed_actual,
            "peak_rps": peak_rps_val,
            "avg_rps": int(self.total_requests / max(1, elapsed_actual)),
            "p95_ms": self._run_p95_ms(),
            "error_pct": round(100 * self._failed_requests / self.total_requests, 1) if self.total_requests else 0.0,
            "metrics_scope": "whole_run",
            "total_requests": self.total_requests,
            "status_2xx": self.status_2xx,
            "status_429": self.status_429,
            "status_5xx": self.status_5xx,
            "bytes_discarded_mb": float(status_snap.get("bytes_discarded_mb", 0.0)),
            "ram_mb": float(status_snap.get("ram_mb", 50.0)),
            "verdict": verdict_cat,
            "status_label": display_status,
            "knee_vus": knee_analysis["knee_vus"],
            "knee_rps": knee_analysis["knee_rps"],
            "knee_p95_ms": knee_analysis["knee_p95_ms"],
            "bottleneck_summary": knee_analysis["bottleneck_summary"],
            "capacity_checked": True,
            "timeseries": self.timeseries_buckets,
            "step_metrics": self.step_metrics,
        }
        save_run(sqlite_record)

        await self.broadcast_telemetry(event=event_type)

    def _run_p95_ms(self):
        if not self.total_requests:
            return 0.0
        rank = (self.total_requests * 95 + 99) // 100
        for latency, count in enumerate(self._latency_counts):
            rank -= count
            if rank <= 0:
                # shortcut: overflow reports the maximum, add finer overflow bins if requests can routinely exceed 60s.
                return self._max_latency_ms if latency == LATENCY_OVERFLOW_MS else latency
        return 0.0

    def _request_headers(self) -> dict:
        return journey_request_headers()

    async def _vu_worker(self, client: httpx.AsyncClient, vu_id: int):
        req_seq = 0

        while not self._stop_event.is_set():
            now = time.time()
            elapsed = now - self.start_time
            if elapsed >= self.duration_sec:
                break

            # Traffic scheduler check: is this VU index active right now?
            active_target = calculate_active_vus(
                self.traffic_mode, self.target_vus, self.duration_sec, elapsed
            )
            if vu_id >= active_target:
                await asyncio.sleep(0.08)
                continue

            req_seq += 1
            request_url = (
                append_cache_buster(self.target_url, vu_id, req_seq)
                if self.cache_bust
                else self.target_url
            )
            headers = self._request_headers()

            status, received, _, latency, timed_out = await self._read_response(client, "GET", request_url, headers)
            self._record_response(status, received, latency, timed_out, 200 <= status < 400)

            # Small inter-request pacing so VUs generate realistic steady throughput
            await asyncio.sleep(0.01)

    async def _vu_journey_worker(self, client: httpx.AsyncClient, vu_id: int):
        req_seq = 0
        while not self._stop_event.is_set():
            now = time.time()
            elapsed = now - self.start_time
            if elapsed >= self.duration_sec:
                break

            active_target = calculate_active_vus(
                self.traffic_mode, self.target_vus, self.duration_sec, elapsed
            )
            if vu_id >= active_target:
                await asyncio.sleep(0.08)
                continue

            context: dict[str, str] = {}

            # Execute sequential steps in journey chain
            for idx, s in enumerate(self.journey_steps):
                if self._stop_event.is_set():
                    break

                req_seq += 1
                try:
                    request_url, headers, body_content = build_journey_request(
                        s, context, parse_target(self.target_url), self.is_sandbox, self.cache_bust, vu_id, req_seq,
                    )
                except JourneyInputError:
                    self.request_stop(f"FAILED (Step {idx + 1}: required journey variable unavailable)")
                    return
                except DestinationError:
                    self.request_stop("STOPPED (DESTINATION_POLICY)")
                    return

                extract_key = s.get("extract_json_key")
                expected_status = s.get("expected_status", 200)
                status_code, received, first_chunk, req_latency, timed_out = await self._read_response(
                    client, s.get("method", "GET").upper(), request_url, headers,
                    body_content, capture=bool(extract_key),
                )
                passed = status_code == expected_status and not self._stop_event.is_set()
                extraction_failed = False
                if passed and extract_key:
                    try:
                        context[extract_key] = extract_journey_value(extract_key, first_chunk)
                    except JourneyInputError:
                        passed = False
                        extraction_failed = True
                is_error = not passed
                self._record_response(status_code, received, req_latency, timed_out, passed)

                # Update per-step metrics
                if idx < len(self.step_metrics):
                    sm = self.step_metrics[idx]
                    sm["requests"] += 1
                    sm["last_status"] = status_code
                    if is_error:
                        sm["failed"] += 1
                    else:
                        sm["passed"] += 1
                    sm["avg_latency_ms"] = round(
                        (sm["avg_latency_ms"] * (sm["requests"] - 1) + req_latency) / sm["requests"], 1
                    )
                if extraction_failed:
                    self.request_stop(f"FAILED (Step {idx + 1}: required response field missing or invalid)")
                    return
                if is_error:
                    break
            else:
                self._successful_journeys += 1

            await asyncio.sleep(0.01)

    def _guard_remaining(self, now: float) -> float:
        return math.inf if self.guard_expires_at is None else self.guard_expires_at - now

    async def _read_response(self, client, method, url, headers, content=None, capture=False):
        guard_remaining = self._guard_remaining(time.time())
        if guard_remaining <= 0:
            self.request_stop("TRIPPED (Guard verification expired)")
            raise asyncio.CancelledError
        started = time.perf_counter()
        status = received = 0
        preview = b""
        timed_out = False
        self._request_vus += 1
        self._peak_vus = max(self._peak_vus, self._request_vus)
        try:
            async with asyncio.timeout(min(self.request_timeout_sec, guard_remaining)):
                async with client.stream(method, url, headers=headers, content=content) as response:
                    status = response.status_code
                    reason = self.brakes.observe_status(time.monotonic(), status, response.headers)
                    if reason:
                        self.request_stop(f"TRIPPED ({reason})")
                    else:
                        async for chunk in response.aiter_bytes(chunk_size=CHUNK_SIZE_BYTES):
                            received += len(chunk)
                            if not preview and (capture or status == 403):
                                preview = chunk
                                reason = self.brakes.observe_preview(status, preview)
                                if reason:
                                    self.request_stop(f"TRIPPED ({reason})")
                                    break
        except (httpx.TimeoutException, TimeoutError):
            if self._guard_remaining(time.time()) <= 0:
                self.request_stop("TRIPPED (Guard verification expired)")
                raise asyncio.CancelledError
            timed_out = True
            status = 0
        except httpx.RequestError:
            status = 0
        finally:
            self._request_vus -= 1
        return status, received, preview, (time.perf_counter() - started) * 1000, timed_out

    def _record_response(self, status, received, latency, timed_out, passed):
        if 200 <= status < 300:
            self.status_2xx += 1
        elif status == 429:
            self.status_429 += 1
        elif 500 <= status < 600:
            self.status_5xx += 1
        else:
            self.status_other += 1
        self.total_requests += 1
        self._failed_requests += not passed
        self._latency_counts[min(LATENCY_OVERFLOW_MS, math.ceil(latency))] += 1
        self._max_latency_ms = max(self._max_latency_ms, latency)
        self.bytes_discarded += received
        now = time.time()
        self._rolling_latencies.append((now, latency))
        self._rolling_requests.append((now, not passed, received))
        self.brakes.observe_timing(time.monotonic(), latency, timed_out)

    async def _circuit_monitor(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(0.5)
            reason = self.brakes.timing_reason(time.monotonic())
            if reason is None and self.get_status()["ram_mb"] > self.ram_limit_mb:
                reason = f"RAM exceeds {self.ram_limit_mb} MB limit"
            if reason:
                self.request_stop(f"TRIPPED ({reason})")
                break


load_engine = LoadEngine()
