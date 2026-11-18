"""
Async Load Engine for Pusher Load Testing Platform.
- httpx.AsyncClient with connection pooling bounded by 70% OS File-Descriptor cap
- 4 KB chunk-discard streaming worker (aiter_bytes(4096) immediately discarded)
- 3 Traffic Modes: Step-Ramp (5 equal steps), Sudden Rush (3s warmup), Steady Crowd (instant 100%)
- Dynamic Cache-Busting (?_cb=nonce)
- Live 1s rolling telemetry and Safety Circuit Breakers (error %, p95 latency, RSS RAM)
"""

import asyncio
import collections
import hashlib
import hmac
import json
import math
import os
import secrets
import sys
import time
import urllib.parse
import httpx
import psutil
from starlette.websockets import WebSocket

# Locked Pusher Invariants
BASE_ENGINE_RAM_MB = 50
RAM_PER_VU_MB = 0.20
DEFAULT_RAM_CEILING_MB = 500
CHUNK_SIZE_BYTES = 4096  # 4 KB chunk discard


class ConnectionManager:
    """Manages active client WebSocket connections for real-time telemetry streaming."""
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        disconnected = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)
        for dead in disconnected:
            if dead in self.active_connections:
                self.active_connections.remove(dead)


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
        step_len = max(1.0, duration_sec / 5.0)
        step_index = min(4, int(elapsed // step_len))
        step_ratios = [0.20, 0.40, 0.60, 0.80, 1.00]
        ratio = step_ratios[step_index]
        return max(1, int(round(target_vus * ratio)))

    elif mode == "sudden_rush":
        if elapsed < 3.0:
            warmup = min(target_vus, max(10, int(round(target_vus * 0.10))))
            return warmup
        return target_vus

    else:  # Default / steady_crowd
        return target_vus


def append_cache_buster(url: str, vu_id: int, req_seq: int) -> str:
    """Append a unique cache-busting query parameter (?_cb=nonce or &_cb=nonce)."""
    nonce = f"{int(time.time() * 1000)}_{vu_id}_{req_seq}"
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}_cb={nonce}"


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
        self.is_running: bool = False
        self.run_id: str | None = None
        self.start_time: float = 0.0
        self.duration_sec: int = 0
        self.target_vus: int = 0
        self.traffic_mode: str = "steady_crowd"
        self.target_url: str = ""
        self.cache_bust: bool = True
        self.active_guard_id: str = ""
        self.handshake_secret: str | None = None
        self.ram_limit_mb: int = DEFAULT_RAM_CEILING_MB
        self.max_error_pct: float = 15.0
        self.p95_ceiling_ms: float = 1500.0
        self.circuit_status: str = "ARMED (Normal)"

        self.use_journey: bool = False
        self.journey_steps: list[dict] = []
        self.step_metrics: list[dict] = []
        self.timeseries_buckets: list[dict] = []

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

        # Rolling 1-second window deques: (timestamp, latency_ms), (timestamp, is_error, bytes)
        self._rolling_latencies = collections.deque()
        self._rolling_requests = collections.deque()

        # Run history archive (Dynamically populated from real runs)
        self.run_history: list[dict] = []

    def get_status(self) -> dict:
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
            calculate_active_vus(self.traffic_mode, self.target_vus, self.duration_sec, elapsed)
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
            "run_history": self.run_history,
        }

    async def start(
        self,
        target_url: str,
        traffic_mode: str,
        target_vus: int,
        duration_sec: int,
        cache_bust: bool = True,
        active_guard_id: str = "PG-ACTIVE",
        handshake_secret: str | None = None,
        ram_limit_mb: int = DEFAULT_RAM_CEILING_MB,
        max_error_pct: float = 15.0,
        p95_ceiling_ms: float = 1500.0,
        use_journey: bool = False,
        journey_steps: list[dict] | None = None,
    ) -> str:
        if self.is_running:
            raise RuntimeError("A load test is already actively running.")

        self.target_url = target_url
        self.traffic_mode = traffic_mode
        self.target_vus = target_vus
        self.duration_sec = duration_sec
        self.cache_bust = cache_bust
        self.active_guard_id = active_guard_id
        self.handshake_secret = handshake_secret
        self.ram_limit_mb = ram_limit_mb
        self.max_error_pct = max_error_pct
        self.p95_ceiling_ms = p95_ceiling_ms
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
                    "path": s.get("path", ""),
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

        self.run_id = f"RUN-{secrets.randbelow(900) + 100}"
        self.start_time = time.time()
        self.is_running = True

        self._stop_event.clear()
        self.total_requests = 0
        self.status_2xx = 0
        self.status_429 = 0
        self.status_5xx = 0
        self.status_other = 0
        self.bytes_discarded = 0
        self._rolling_latencies.clear()
        self._rolling_requests.clear()
        self.timeseries_buckets = []

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
        await self.connection_manager.broadcast(status)

    def stop(self, reason: str = "MANUAL_ABORT"):
        if not self.is_running:
            return
        self.circuit_status = f"STOPPED ({reason})"
        self._stop_event.set()
        self.is_running = False
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast_telemetry(event="STOP"))
        except RuntimeError:
            pass

    def simulate_spike(self) -> dict:
        """
        Live Backend WAF/5xx Fault Injector:
        Injects a burst of simulated 429 WAF and 503 Service Unavailable responses into
        the live telemetry window, causing the backend circuit breaker to trip immediately.
        """
        if not self.is_running:
            raise RuntimeError("No active load test is running to inject faults.")

        now = time.time()
        # Burst of 30 errors: 15 WAF rate-limits (429) + 15 Server Errors (503)
        for _ in range(30):
            self._rolling_requests.append((now, True, 4096))
            self._rolling_latencies.append((now, 920.0))
        self.status_429 += 15
        self.status_5xx += 15
        self.total_requests += 30

        self.circuit_status = "TRIPPED (429/5xx Spike Auto-Abort)"
        self._stop_event.set()
        self.is_running = False

        now_str = time.strftime("%H:%M:%S")
        elapsed_actual = min(int(now - self.start_time), self.duration_sec)
        status_snap = self.get_status()

        from backend.core.report_service import detect_knee_of_curve, save_run
        knee_analysis = detect_knee_of_curve(self.timeseries_buckets, self.target_vus, self.p95_ceiling_ms)

        sqlite_record = {
            "run_id": self.run_id,
            "timestamp": now_str,
            "target_url": self.target_url,
            "guard_id": self.active_guard_id,
            "mode": self.traffic_mode.replace("_", " ").title(),
            "target_vus": self.target_vus,
            "peak_vus": self.target_vus,
            "duration_sec": self.duration_sec,
            "elapsed_sec": elapsed_actual,
            "peak_rps": len(self._rolling_requests),
            "avg_rps": int(self.total_requests / max(1, elapsed_actual)),
            "p95_ms": float(status_snap["p95_ms"]),
            "error_pct": float(status_snap["error_pct"]),
            "total_requests": self.total_requests,
            "status_2xx": self.status_2xx,
            "status_429": self.status_429,
            "status_5xx": self.status_5xx,
            "bytes_discarded_mb": float(status_snap.get("bytes_discarded_mb", 0.0)),
            "ram_mb": float(status_snap.get("ram_mb", 50.0)),
            "verdict": "CIRCUIT_TRIPPED",
            "status_label": "AUTO-ABORTED (429/5xx Circuit Breaker Tripped)",
            "knee_vus": knee_analysis["knee_vus"],
            "knee_rps": knee_analysis["knee_rps"],
            "knee_p95_ms": knee_analysis["knee_p95_ms"],
            "bottleneck_summary": knee_analysis["bottleneck_summary"],
            "timeseries": self.timeseries_buckets,
            "step_metrics": self.step_metrics,
        }
        save_run(sqlite_record)

        record = {
            "id": self.run_id,
            "timestamp": now_str,
            "target": self.target_url,
            "guardToken": self.active_guard_id,
            "mode": self.traffic_mode.replace("_", " ").title(),
            "peakVus": self.target_vus,
            "duration": elapsed_actual,
            "peakRps": len(self._rolling_requests),
            "p95": f"{int(self.get_status()['p95_ms'])} ms",
            "status": "AUTO-ABORTED (429/5xx Circuit Breaker Tripped)",
            "verdictCategory": "CIRCUIT_BREAKER",
        }
        self.run_history.insert(0, record)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast_telemetry(event="CIRCUIT_TRIPPED"))
        except RuntimeError:
            pass

        return {
            "status": "tripped",
            "circuit_status": self.circuit_status,
            "run_id": self.run_id,
        }

    async def _run_orchestrator(self):
        fd_cap = get_os_fd_cap()
        capped_vus = min(self.target_vus, fd_cap)

        limits = httpx.Limits(max_connections=capped_vus, max_keepalive_connections=capped_vus)
        timeout = httpx.Timeout(10.0, connect=5.0)

        async with httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=True) as client:
            if self.use_journey and self.journey_steps:
                self._worker_tasks = [
                    asyncio.create_task(self._vu_journey_worker(client, vu_index))
                    for vu_index in range(self.target_vus)
                ]
            else:
                self._worker_tasks = [
                    asyncio.create_task(self._vu_worker(client, vu_index))
                    for vu_index in range(self.target_vus)
                ]

            # Monitor loop running concurrently
            monitor_task = asyncio.create_task(self._circuit_monitor())

            try:
                # Wait until duration expires or stop_event is set; broadcast 1s TICK
                last_tick = time.time()
                while not self._stop_event.is_set():
                    now = time.time()
                    elapsed = now - self.start_time
                    if elapsed >= self.duration_sec:
                        break
                    if now - last_tick >= 1.0:
                        last_tick = now
                        status_snap = self.get_status()
                        self.timeseries_buckets.append({
                            "elapsed_sec": int(elapsed),
                            "vus": status_snap["active_vus"],
                            "rps": status_snap["live_rps"],
                            "p95_ms": status_snap["p95_ms"],
                            "error_pct": status_snap["error_pct"],
                        })
                        await self.broadcast_telemetry(event="TICK")
                    await asyncio.sleep(0.1)
            finally:
                self._stop_event.set()
                monitor_task.cancel()
                if self._worker_tasks:
                    await asyncio.gather(*self._worker_tasks, return_exceptions=True)
                self.is_running = False

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
                else:
                    verdict_cat = "PASSED"
                    display_status = f"PASSED (Completed {self.duration_sec}s)"
                    event_type = "COMPLETE"

                now_str = time.strftime("%H:%M:%S")
                status_snap = self.get_status()
                elapsed_actual = min(int(time.time() - self.start_time), self.duration_sec)

                from backend.core.report_service import detect_knee_of_curve, save_run
                knee_analysis = detect_knee_of_curve(self.timeseries_buckets, self.target_vus, self.p95_ceiling_ms)

                peak_rps_val = max(
                    [b.get("rps", 0) for b in self.timeseries_buckets] + [status_snap["live_rps"], len(self._rolling_requests)]
                )

                sqlite_record = {
                    "run_id": self.run_id,
                    "timestamp": now_str,
                    "target_url": self.target_url,
                    "guard_id": self.active_guard_id,
                    "mode": self.traffic_mode.replace("_", " ").title(),
                    "target_vus": self.target_vus,
                    "peak_vus": self.target_vus,
                    "duration_sec": self.duration_sec,
                    "elapsed_sec": elapsed_actual,
                    "peak_rps": peak_rps_val,
                    "avg_rps": int(self.total_requests / max(1, elapsed_actual)),
                    "p95_ms": status_snap["p95_ms"],
                    "error_pct": status_snap["error_pct"],
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
                    "timeseries": self.timeseries_buckets,
                    "step_metrics": self.step_metrics,
                }
                save_run(sqlite_record)

                record = {
                    "id": self.run_id,
                    "timestamp": now_str,
                    "target": self.target_url,
                    "guardToken": self.active_guard_id,
                    "mode": self.traffic_mode.replace("_", " ").title(),
                    "peakVus": self.target_vus,
                    "duration": elapsed_actual,
                    "peakRps": peak_rps_val,
                    "p95": f"{int(status_snap['p95_ms'])} ms",
                    "status": display_status,
                    "verdictCategory": verdict_cat,
                }
                if not any(r.get("id") == self.run_id for r in self.run_history):
                    self.run_history.insert(0, record)

                await self.broadcast_telemetry(event=event_type)

    def _build_signed_headers(self) -> dict:
        guard_id = self.active_guard_id or "PG-ACTIVE"
        from backend.core.target_service import target_store
        secret = self.handshake_secret or target_store.bypass_secret or "bypass_secret_demo"
        curr_min = str(int(time.time() // 60))
        sig = hmac.new(
            secret.encode("utf-8"),
            f"{guard_id}:{curr_min}".encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return {
            "X-Pusher-Guard-ID": guard_id,
            "X-Pusher-Timestamp": curr_min,
            "X-Pusher-Signature": sig,
            "X-Pusher-Bypass": f"{guard_id}-SIGNED",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "User-Agent": "Pusher-LoadEngine/1.0",
        }

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
            headers = self._build_signed_headers()

            req_t0 = time.perf_counter()
            is_error = False
            bytes_read = 0

            try:
                # 4 KB Chunk-Discard Streaming Worker
                async with client.stream("GET", request_url, headers=headers) as response:
                    status_code = response.status_code
                    async for chunk in response.aiter_bytes(chunk_size=CHUNK_SIZE_BYTES):
                        bytes_read += len(chunk)
                        # Immediately discard chunk to avoid memory bloat
                    
                    req_latency = (time.perf_counter() - req_t0) * 1000.0

                    # Classify status
                    if 200 <= status_code < 400:
                        self.status_2xx += 1
                    elif status_code == 429:
                        self.status_429 += 1
                        is_error = True
                    elif 500 <= status_code < 600:
                        self.status_5xx += 1
                        is_error = True
                    else:
                        self.status_other += 1

            except (httpx.TimeoutException, httpx.RequestError):
                req_latency = (time.perf_counter() - req_t0) * 1000.0
                self.status_5xx += 1
                is_error = True

            self.total_requests += 1
            self.bytes_discarded += bytes_read

            record_time = time.time()
            self._rolling_latencies.append((record_time, req_latency))
            self._rolling_requests.append((record_time, is_error, bytes_read))

            # Small inter-request pacing so VUs generate realistic steady throughput
            await asyncio.sleep(0.01)

    async def _vu_journey_worker(self, client: httpx.AsyncClient, vu_id: int):
        req_seq = 0
        context: dict[str, str] = {}

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

            cycle_aborted = False

            # Execute sequential steps in journey chain
            for idx, s in enumerate(self.journey_steps):
                if self._stop_event.is_set() or cycle_aborted:
                    break

                req_seq += 1
                raw_path = s.get("path", "")
                resolved_path = raw_path
                for k, v in context.items():
                    resolved_path = resolved_path.replace(f"{{{{{k}}}}}", str(v))

                if resolved_path.startswith("http://") or resolved_path.startswith("https://"):
                    base_req_url = resolved_path
                else:
                    clean_base = self.target_url.rstrip("/")
                    clean_path = resolved_path.lstrip("/")
                    base_req_url = f"{clean_base}/{clean_path}"

                request_url = (
                    append_cache_buster(base_req_url, vu_id, req_seq)
                    if self.cache_bust
                    else base_req_url
                )

                # Headers with token interpolation & signed guard headers
                headers = self._build_signed_headers()
                for hk, hv in (s.get("headers") or {}).items():
                    val = str(hv)
                    for ck, cv in context.items():
                        val = val.replace(f"{{{{{ck}}}}}", str(cv))
                    headers[hk] = val

                body_content = s.get("body")
                if body_content:
                    for ck, cv in context.items():
                        body_content = body_content.replace(f"{{{{{ck}}}}}", str(cv))

                req_t0 = time.perf_counter()
                is_error = False
                bytes_read = 0
                first_chunk = b""
                status_code = 0
                extract_key = s.get("extract_json_key")
                expected_status = s.get("expected_status", 200)

                try:
                    async with client.stream(
                        method=s.get("method", "GET"),
                        url=request_url,
                        headers=headers,
                        content=body_content.encode("utf-8") if body_content else None,
                    ) as response:
                        status_code = response.status_code
                        async for chunk in response.aiter_bytes(chunk_size=CHUNK_SIZE_BYTES):
                            if not first_chunk and extract_key:
                                first_chunk = chunk
                            bytes_read += len(chunk)
                            # Discard chunk immediately to maintain strict 0.20 MB/VU memory cap

                        req_latency = (time.perf_counter() - req_t0) * 1000.0

                        if status_code == expected_status or (expected_status == 200 and status_code in (200, 201)):
                            self.status_2xx += 1
                            if extract_key and first_chunk:
                                try:
                                    parsed = json.loads(first_chunk.decode("utf-8", errors="ignore"))
                                    if isinstance(parsed, dict) and extract_key in parsed:
                                        context[extract_key] = str(parsed[extract_key])
                                except Exception:
                                    pass
                        elif status_code == 429:
                            self.status_429 += 1
                            is_error = True
                            cycle_aborted = True
                        elif 500 <= status_code < 600:
                            self.status_5xx += 1
                            is_error = True
                            cycle_aborted = True
                        else:
                            self.status_other += 1
                            is_error = True
                            cycle_aborted = True

                except (httpx.TimeoutException, httpx.RequestError):
                    req_latency = (time.perf_counter() - req_t0) * 1000.0
                    self.status_5xx += 1
                    is_error = True
                    cycle_aborted = True

                self.total_requests += 1
                self.bytes_discarded += bytes_read

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

                record_time = time.time()
                self._rolling_latencies.append((record_time, req_latency))
                self._rolling_requests.append((record_time, is_error, bytes_read))

            await asyncio.sleep(0.01)

    async def _circuit_monitor(self):
        """Monitor rolling metrics and trip safety circuit breaker when thresholds breached."""
        while not self._stop_event.is_set():
            await asyncio.sleep(0.5)
            if self.total_requests < 20:
                continue

            status = self.get_status()

            # 1. Error Rate Circuit Breaker
            if status["error_pct"] > self.max_error_pct:
                self.circuit_status = f"TRIPPED (Error rate {status['error_pct']}% > {self.max_error_pct}%)"
                self._stop_event.set()
                break

            # 2. Latency Ceiling Circuit Breaker
            if status["p95_ms"] > self.p95_ceiling_ms:
                self.circuit_status = f"TRIPPED (p95 latency {status['p95_ms']}ms > {self.p95_ceiling_ms}ms)"
                self._stop_event.set()
                break

            # 3. Process RSS Memory Limit Check
            if status["ram_mb"] > self.ram_limit_mb:
                self.circuit_status = f"TRIPPED (RAM {status['ram_mb']}MB > {self.ram_limit_mb}MB limit)"
                self._stop_event.set()
                break


load_engine = LoadEngine()
