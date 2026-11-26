"""
Standalone spawn-safe worker process for Pusher's multi-process load generator (SCALE-01).
Runs an isolated asyncio event loop + connection pool for a sliced VU shard and streams
compact metric deltas back to the coordinator LoadEngine over multiprocessing IPC.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
import math
import os
import time
from typing import Any

import psutil

from backend.core.circuit_breakers import CircuitBreakers
from backend.core.crash_diagnosis import classify_error_code
from backend.core.http_runner import AiohttpLoadClient, get_fast_loop_factory
from backend.core.journey_service import (
    JourneyInputError,
    compile_journey_step,
    extract_journey_value,
    journey_request_headers,
)
from backend.core.target_policy import DestinationError, parse_target

CHUNK_SIZE_BYTES = 4096
LATENCY_OVERFLOW_MS = 60_001
DELTA_FLUSH_INTERVAL_SEC = 0.20


def worker_active_target(
    traffic_mode: str,
    global_target_vus: int,
    duration_sec: int,
    elapsed: float,
    worker_id: int,
    worker_count: int,
    max_worker_vus: int,
) -> int:
    """Compute this worker's exact active VU count so aggregate VUs sum cleanly across shards."""
    from backend.core.load_engine import calculate_active_vus

    global_active = calculate_active_vus(traffic_mode, global_target_vus, duration_sec, elapsed)
    base, rem = divmod(global_active, max(1, worker_count))
    shard = base + (1 if worker_id < rem else 0)
    return min(max_worker_vus, shard)


class _ProcessWorkerRunner:
    def __init__(self, config: dict[str, Any], delta_queue: Any, mp_stop_event: Any, mp_start_event: Any = None) -> None:
        from backend.core.config import settings
        if config.get("pusher_mode"):
            settings.pusher_mode = str(config["pusher_mode"])
        if config.get("sandbox_port") is not None:
            settings.port = int(config["sandbox_port"])

        self.worker_id: int = int(config["worker_id"])
        self.worker_count: int = int(config["worker_count"])
        self.target_url: str = str(config["target_url"])
        self._parsed_target = parse_target(self.target_url)
        self.is_sandbox: bool = bool(config.get("is_sandbox", False))
        self.traffic_mode: str = str(config.get("traffic_mode", "steady_crowd"))
        self.global_target_vus: int = int(config["global_target_vus"])
        self.worker_vu_cap: int = max(1, int(config["worker_vu_cap"]))
        self.duration_sec: int = int(config["duration_sec"])
        self.start_time: float = float(config["start_time"])
        self.cache_bust: bool = bool(config.get("cache_bust", True))
        self.max_error_pct: float = float(config.get("max_error_pct", 5.0))
        self.p95_ceiling_ms: float = float(config.get("p95_ceiling_ms", 1500.0))
        self.request_timeout_sec: float = float(config.get("request_timeout_sec", 5.0))
        self.guard_expires_at: float | None = config.get("guard_expires_at")
        self.use_journey: bool = bool(config.get("use_journey", False))
        self.journey_steps: list[dict[str, Any]] = list(config.get("journey_steps") or [])
        self._static_headers: dict[str, str] = journey_request_headers()
        self._run_epoch_ms: int = int(self.start_time * 1000)
        cb_sep = "&" if "?" in self.target_url else "?"
        self._cb_prefix: str = f"{self.target_url}{cb_sep}_cb={self._run_epoch_ms}_{self.worker_id}_"
        self._compiled_steps = (
            [compile_journey_step(s, self._parsed_target, self.is_sandbox) for s in self.journey_steps]
            if (self.use_journey and self.journey_steps)
            else []
        )

        self.delta_queue = delta_queue
        self.mp_stop_event = mp_stop_event
        self.mp_start_event = mp_start_event
        self.local_stop = asyncio.Event()
        self._vu_wake_event = asyncio.Event()
        self.brakes = CircuitBreakers(self.max_error_pct, self.p95_ceiling_ms, target_vus=self.global_target_vus)
        self.trip_reason: str | None = None
        self.scaling_paused: bool = False
        self.loop_lag_ms: float = 0.0
        self._process = psutil.Process(os.getpid())
        self._worker_tasks: list[asyncio.Task] = []
        self._last_timing_check: float = 0.0

        # Interval accumulators (cleared on each IPC flush)
        self._inflight: int = 0
        self._inflight_peak: int = 0
        self._d_total: int = 0
        self._d_2xx: int = 0
        self._d_3xx: int = 0
        self._d_4xx: int = 0
        self._d_429: int = 0
        self._d_5xx: int = 0
        self._d_timeouts: int = 0
        self._d_network_errors: int = 0
        self._d_other: int = 0
        self._d_failed: int = 0
        self._d_successful_journeys: int = 0
        self._d_bytes: int = 0
        self._d_cache_hits: int = 0
        self._d_max_latency: float = 0.0
        self._d_buckets: dict[int, int] = defaultdict(int)
        self._d_tenths_buckets: dict[int, int] = defaultdict(int)
        self._d_overflow: list[float] = []
        self._d_breaker_samples: list[tuple[int, float, int]] = []
        self._d_step_stats: dict[int, list[Any]] = {}
        self._d_part_stats: dict[str, dict[str, Any]] = {}

    def _wake_workers(self) -> None:
        ev = self._vu_wake_event
        ev.set()
        self._vu_wake_event = asyncio.Event()

    def _guard_remaining(self, now: float) -> float:
        return math.inf if self.guard_expires_at is None else self.guard_expires_at - now

    def _trigger_trip(self, reason: str) -> None:
        if self.trip_reason is None:
            self.trip_reason = reason
        self.local_stop.set()
        self._wake_workers()

    def _record(
        self,
        status: int,
        received: int,
        latency_ms: float,
        timed_out: bool,
        passed: bool,
    ) -> None:
        if 200 <= status < 300:
            self._d_2xx += 1
        elif 300 <= status < 400:
            self._d_3xx += 1
        elif status == 429:
            self._d_429 += 1
        elif 400 <= status < 500:
            self._d_4xx += 1
        elif 500 <= status < 600:
            self._d_5xx += 1
        elif timed_out:
            self._d_timeouts += 1
        elif status == 0:
            self._d_network_errors += 1
        else:
            self._d_other += 1

        self._d_total += 1
        if not passed:
            self._d_failed += 1
        self._d_bytes += received
        if (self._d_total <= 48 or (self._d_total & 3) == 0) and len(self._d_breaker_samples) < 64:
            self._d_breaker_samples.append((status, round(latency_ms, 2), 1 if timed_out else 0))

        if status != 0 or timed_out:
            bucket = min(LATENCY_OVERFLOW_MS, max(0, math.ceil(latency_ms)))
            self._d_buckets[bucket] += 1
            tenths = min(600_000, max(0, round(latency_ms * 10.0)))
            self._d_tenths_buckets[tenths] += 1
            if bucket == LATENCY_OVERFLOW_MS and len(self._d_overflow) < 2000:
                self._d_overflow.append(latency_ms)
            self._d_max_latency = max(self._d_max_latency, latency_ms)

            mono_now = time.monotonic()
            self.brakes.observe_timing(mono_now, latency_ms, timed_out)
            if len(self.brakes.timings) >= 20 and (
                timed_out
                or latency_ms > self.brakes.latency_limit
                or mono_now - self._last_timing_check >= 0.1
            ):
                self._last_timing_check = mono_now
                reason = self.brakes.timing_reason(mono_now)
                if reason:
                    self._trigger_trip(f"TRIPPED ({reason})")

    def _record_step(self, idx: int, status_code: int, req_latency: float, is_error: bool) -> None:
        entry = self._d_step_stats.get(idx)
        if entry is None:
            entry = [0, 0, 0, 0.0, 0]
            self._d_step_stats[idx] = entry
        entry[0] += 1
        if is_error:
            entry[2] += 1
        else:
            entry[1] += 1
        entry[3] += req_latency
        entry[4] = status_code

    def _record_part(
        self,
        part_key: str,
        part_name: str,
        method: str,
        path: str,
        status_code: int,
        req_latency: float,
        timed_out: bool,
        is_error: bool,
        elapsed_sec: int,
        active_vus: int,
        error_code_override: str | None = None,
    ) -> None:
        entry = self._d_part_stats.get(part_key)
        if entry is None:
            entry = {
                "part_name": part_name,
                "method": method,
                "path": path,
                "total": 0,
                "failed": 0,
                "lat_sum": 0.0,
                "lat_count": 0,
                "buckets": defaultdict(int),
                "codes": {},
                "first_err_sec": None,
                "first_err_vus": None,
            }
            self._d_part_stats[part_key] = entry
        entry["total"] += 1
        if status_code != 0 or timed_out:
            entry["lat_sum"] += req_latency
            entry["lat_count"] += 1
            b = min(LATENCY_OVERFLOW_MS, max(0, math.ceil(req_latency)))
            entry["buckets"][b] += 1
        if is_error:
            entry["failed"] += 1
            code_key = error_code_override or classify_error_code(status_code, timed_out)
            entry["codes"][code_key] = entry["codes"].get(code_key, 0) + 1
            sec_i = max(0, int(elapsed_sec))
            vu_i = max(1, int(active_vus))
            if entry["first_err_sec"] is None or sec_i < entry["first_err_sec"]:
                entry["first_err_sec"] = sec_i
                entry["first_err_vus"] = vu_i

    async def _read_response(
        self,
        client: AiohttpLoadClient,
        method: str,
        url: str,
        headers: dict[str, str],
        content: bytes | None = None,
        capture: bool = False,
    ) -> tuple[int, int, bytes, float, bool]:
        guard_remaining = self._guard_remaining(time.time())
        if guard_remaining <= 0:
            self._trigger_trip("TRIPPED (Guard verification expired)")
            raise asyncio.CancelledError
        started = time.perf_counter()
        self._inflight += 1
        if self._inflight > self._inflight_peak:
            self._inflight_peak = self._inflight
        try:
            status, received, preview, timed_out = await client.execute_request(
                method,
                url,
                headers,
                content=content,
                capture=capture,
                deadline_sec=guard_remaining,
                brakes=self.brakes,
                on_trip=self._trigger_trip,
                on_cache_hit=self._record_cache_hit,
            )
            if timed_out and self._guard_remaining(time.time()) <= 0:
                self._trigger_trip("TRIPPED (Guard verification expired)")
                raise asyncio.CancelledError
        finally:
            self._inflight = max(0, self._inflight - 1)
        return status, received, preview, (time.perf_counter() - started) * 1000.0, timed_out

    def _record_cache_hit(self) -> None:
        self._d_cache_hits += 1

    async def _vu_worker(self, client: AiohttpLoadClient, vu_id: int) -> None:
        req_seq = 0
        static_url = self.target_url
        cb_prefix = self._cb_prefix
        use_cb = self.cache_bust
        headers = self._static_headers
        if self.global_target_vus >= 64:
            stagger_slots = 250 if self.global_target_vus >= 500 else 64
            await asyncio.sleep(((self.worker_id * 17 + vu_id) % stagger_slots) * 0.004)

        while not self.local_stop.is_set() and not self.mp_stop_event.is_set():
            elapsed = time.time() - self.start_time
            if elapsed >= self.duration_sec:
                break
            active_target = worker_active_target(
                self.traffic_mode,
                self.global_target_vus,
                self.duration_sec,
                elapsed,
                self.worker_id,
                self.worker_count,
                self.worker_vu_cap,
            )
            if vu_id >= active_target:
                await self._vu_wake_event.wait()
                continue

            req_seq += 1
            request_url = f"{cb_prefix}{vu_id}_{req_seq}" if use_cb else static_url
            status, received, _, latency_ms, timed_out = await self._read_response(
                client, "GET", request_url, headers
            )
            passed = 200 <= status < 400
            self._record(status, received, latency_ms, timed_out, passed)
            single_path = self._parsed_target.path or "/"
            self._record_part(
                "0",
                f"GET {single_path}",
                "GET",
                single_path,
                status,
                latency_ms,
                timed_out,
                not passed,
                elapsed,
                max(active_target * max(1, self.worker_count), 1),
            )
            await asyncio.sleep(0.01)

    async def _vu_journey_worker(self, client: AiohttpLoadClient, vu_id: int) -> None:
        req_seq = 0
        compiled_steps = self._compiled_steps
        epoch_ms = self._run_epoch_ms
        while not self.local_stop.is_set() and not self.mp_stop_event.is_set():
            elapsed = time.time() - self.start_time
            if elapsed >= self.duration_sec:
                break
            active_target = worker_active_target(
                self.traffic_mode,
                self.global_target_vus,
                self.duration_sec,
                elapsed,
                self.worker_id,
                self.worker_count,
                self.worker_vu_cap,
            )
            if vu_id >= active_target:
                await self._vu_wake_event.wait()
                continue

            context: dict[str, str] = {}
            for idx, step in enumerate(compiled_steps):
                if self.local_stop.is_set() or self.mp_stop_event.is_set():
                    break
                req_seq += 1
                try:
                    request_url, headers, body_content = step.build(
                        context, self.cache_bust, vu_id, req_seq, epoch_ms
                    )
                except JourneyInputError:
                    self._trigger_trip(f"FAILED (Step {idx + 1}: required journey variable unavailable)")
                    return
                except DestinationError:
                    self._trigger_trip("STOPPED (DESTINATION_POLICY)")
                    return

                extract_key = step.extract_key
                expected_status = step.expected_status
                status_code, received, first_chunk, req_latency, timed_out = await self._read_response(
                    client,
                    step.method,
                    request_url,
                    headers,
                    body_content,
                    capture=bool(extract_key),
                )
                passed = status_code == expected_status and not self.local_stop.is_set()
                extraction_failed = False
                if passed and extract_key:
                    try:
                        context[extract_key] = extract_journey_value(extract_key, first_chunk)
                    except JourneyInputError:
                        passed = False
                        extraction_failed = True
                is_error = not passed
                self._record(status_code, received, req_latency, timed_out, passed)
                self._record_step(idx, status_code, req_latency, is_error)
                step_meta = self.journey_steps[idx] if idx < len(self.journey_steps) else {}
                raw_step_path = step_meta.get("path") or step.raw_path or "/"
                step_label = step_meta.get("name") or f"Step {idx + 1}: {step.method} {raw_step_path}"
                step_path = raw_step_path.split("#", 1)[0].partition("?")[0] or "/"
                self._record_part(
                    str(idx),
                    step_label,
                    step.method,
                    step_path,
                    status_code,
                    req_latency,
                    timed_out,
                    is_error,
                    elapsed,
                    max(active_target * max(1, self.worker_count), 1),
                    error_code_override="EXTRACTION_FAILED" if extraction_failed else None,
                )
                if extraction_failed:
                    self._trigger_trip(f"FAILED (Step {idx + 1}: required response field missing or invalid)")
                    return
                if is_error:
                    break
            else:
                self._d_successful_journeys += 1

            await asyncio.sleep(0.01)

    def _ensure_workers(self, client: httpx.AsyncClient, worker_fn, active_target: int) -> None:
        desired = min(self.worker_vu_cap, max(0, active_target))
        while len(self._worker_tasks) < desired and not self.local_stop.is_set():
            vu_id = len(self._worker_tasks)
            task = asyncio.create_task(worker_fn(client, vu_id))
            self._worker_tasks.append(task)

    def _flush_delta(self, force: bool = False) -> None:
        if not force and self._d_total == 0 and self._inflight == 0 and self.trip_reason is None:
            return
        try:
            rss_mb = round(self._process.memory_info().rss / (1024 * 1024), 1)
        except Exception:
            rss_mb = 35.0
        payload = {
            "type": "delta",
            "worker_id": self.worker_id,
            "ts": time.time(),
            "total_requests": self._d_total,
            "status_2xx": self._d_2xx,
            "status_3xx": self._d_3xx,
            "status_4xx": self._d_4xx,
            "status_429": self._d_429,
            "status_5xx": self._d_5xx,
            "timeout_count": self._d_timeouts,
            "network_error_count": self._d_network_errors,
            "status_other": self._d_other,
            "failed_requests": self._d_failed,
            "successful_journeys": self._d_successful_journeys,
            "bytes_discarded": self._d_bytes,
            "cache_hit_count": self._d_cache_hits,
            "inflight": self._inflight,
            "inflight_peak": self._inflight_peak,
            "max_latency_ms": self._d_max_latency,
            "latency_buckets": list(self._d_buckets.items()),
            "rolling_tenths": list(self._d_tenths_buckets.items()),
            "overflow_latencies": self._d_overflow,
            "breaker_samples": self._d_breaker_samples,
            "step_deltas": {idx: list(vals) for idx, vals in self._d_step_stats.items()},
            "part_deltas": {
                k: {
                    "part_name": v["part_name"],
                    "method": v["method"],
                    "path": v["path"],
                    "total": v["total"],
                    "failed": v["failed"],
                    "lat_sum": v["lat_sum"],
                    "lat_count": v["lat_count"],
                    "buckets": list(v["buckets"].items()),
                    "codes": v["codes"],
                    "first_err_sec": v["first_err_sec"],
                    "first_err_vus": v["first_err_vus"],
                }
                for k, v in self._d_part_stats.items()
            },
            "rss_mb": rss_mb,
            "loop_lag_ms": self.loop_lag_ms,
            "trip_reason": self.trip_reason,
        }
        self._d_total = 0
        self._d_2xx = 0
        self._d_3xx = 0
        self._d_4xx = 0
        self._d_429 = 0
        self._d_5xx = 0
        self._d_timeouts = 0
        self._d_network_errors = 0
        self._d_other = 0
        self._d_failed = 0
        self._d_successful_journeys = 0
        self._d_bytes = 0
        self._d_cache_hits = 0
        self._d_max_latency = 0.0
        self._inflight_peak = self._inflight
        self._d_buckets.clear()
        self._d_tenths_buckets.clear()
        self._d_overflow = []
        self._d_breaker_samples = []
        self._d_step_stats.clear()
        self._d_part_stats.clear()
        try:
            self.delta_queue.put_nowait(payload)
        except Exception:
            pass

    async def run(self) -> None:
        try:
            async with AiohttpLoadClient(
                self._parsed_target,
                self.is_sandbox,
                timeout=self.request_timeout_sec,
                connections=self.worker_vu_cap,
            ) as client:
                try:
                    self.delta_queue.put_nowait({"type": "ready", "worker_id": self.worker_id})
                except Exception:
                    pass
                if self.mp_start_event is not None:
                    while not self.mp_start_event.is_set() and not self.mp_stop_event.is_set():
                        await asyncio.sleep(0.01)
                    self.start_time = time.time()
                if self.mp_stop_event.is_set():
                    return
                worker_fn = self._vu_journey_worker if self.use_journey and self.journey_steps else self._vu_worker
                initial = worker_active_target(
                    self.traffic_mode,
                    self.global_target_vus,
                    self.duration_sec,
                    max(0.0, time.time() - self.start_time),
                    self.worker_id,
                    self.worker_count,
                    self.worker_vu_cap,
                )
                self._ensure_workers(client, worker_fn, initial)
                last_flush = time.monotonic()
                high_lag_since: float | None = None
                while not self.local_stop.is_set() and not self.mp_stop_event.is_set():
                    wall = time.time()
                    elapsed = wall - self.start_time
                    remaining = self.duration_sec - elapsed
                    guard_remaining = self._guard_remaining(wall)
                    if remaining <= 0 or guard_remaining <= 0:
                        if guard_remaining <= 0:
                            self._trigger_trip("TRIPPED (Guard verification expired)")
                        break
                    if not self.scaling_paused:
                        desired = worker_active_target(
                            self.traffic_mode,
                            self.global_target_vus,
                            self.duration_sec,
                            elapsed,
                            self.worker_id,
                            self.worker_count,
                            self.worker_vu_cap,
                        )
                        prev = len(self._worker_tasks)
                        self._ensure_workers(client, worker_fn, desired)
                        if desired > prev:
                            self._wake_workers()

                    mono = time.monotonic()
                    if mono - last_flush >= DELTA_FLUSH_INTERVAL_SEC:
                        last_flush = mono
                        self._flush_delta()

                    sleep_for = min(remaining, guard_remaining, DELTA_FLUSH_INTERVAL_SEC)
                    t0 = time.perf_counter()
                    try:
                        await asyncio.wait_for(self.local_stop.wait(), timeout=max(0.01, sleep_for))
                    except TimeoutError:
                        perf_now = time.perf_counter()
                        lag_ms = max(0.0, ((perf_now - t0) - max(0.01, sleep_for)) * 1000.0)
                        self.loop_lag_ms = round(lag_ms, 1)
                        if lag_ms > 200.0:
                            if high_lag_since is None:
                                high_lag_since = perf_now
                            elif perf_now - high_lag_since >= 5.0:
                                self.scaling_paused = True
                        else:
                            high_lag_since = None
                            self.scaling_paused = False
        except Exception as exc:
            self._trigger_trip(f"STOPPED (WORKER_ERROR: {type(exc).__name__})")
        finally:
            self.local_stop.set()
            self._wake_workers()
            for task in self._worker_tasks:
                task.cancel()
            if self._worker_tasks:
                await asyncio.gather(*self._worker_tasks, return_exceptions=True)
            self._worker_tasks = []
            self._flush_delta(force=True)
            try:
                self.delta_queue.put_nowait({
                    "type": "done",
                    "worker_id": self.worker_id,
                    "trip_reason": self.trip_reason,
                })
            except Exception:
                pass


def run_worker_process(
    config: dict[str, Any], delta_queue: Any, mp_stop_event: Any, mp_start_event: Any = None
) -> None:
    """Spawned child-process entrypoint for a multi-process LoadEngine worker shard."""
    runner = _ProcessWorkerRunner(config, delta_queue, mp_stop_event, mp_start_event)
    loop_factory = get_fast_loop_factory()
    try:
        if loop_factory is not None:
            asyncio.run(runner.run(), loop_factory=loop_factory)
        else:
            asyncio.run(runner.run())
    except KeyboardInterrupt:
        pass
