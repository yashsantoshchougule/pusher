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
from datetime import datetime, timezone
import inspect
import math
import multiprocessing as mp
import os
import queue
from uuid import uuid4
import sys
import time
from time import monotonic_ns
from typing import Any
import httpx
import psutil
from starlette.websockets import WebSocket

from backend.core.circuit_breakers import MAX_ERROR_PCT_CAP, MAX_P95_CEILING_MS, CircuitBreakers
from backend.core.crash_diagnosis import classify_error_code, compute_crash_diagnosis
from backend.core.http_runner import AiohttpLoadClient
from backend.core.journey_service import (
    JourneyInputError,
    append_cache_buster,
    build_journey_request,
    compile_journey_step,
    extract_journey_value,
    journey_request_headers,
)
from backend.core.request_owner import request_owner
from backend.core.target_policy import DestinationError, parse_target, target_client
from backend.core.worker_process import run_worker_process

_DEFAULT_TARGET_CLIENT = target_client
_DEFAULT_TIME_MODULE = time

# Locked Pusher Invariants
BASE_ENGINE_RAM_MB = 50
RAM_PER_VU_MB = 0.20
DEFAULT_RAM_CEILING_MB = 500
DEFAULT_MAX_ERROR_PCT = 5.0
MAX_REQUESTED_VUS = 100_000
CHUNK_SIZE_BYTES = 4096  # 4 KB chunk discard
LATENCY_OVERFLOW_MS = 60_001
WINDOWS_SOCKET_SOFT_LIMIT = 10000
WINDOWS_SOCKET_HARD_LIMIT = 16384
MAX_PROCESS_WORKERS = min(8, os.cpu_count() or 1)
MULTIPROCESS_VU_THRESHOLD = 128
MP_COORDINATOR_RESERVE_MB = 120
MP_WORKER_PROCESS_MB = 85
ROLLING_MAX_TENTHS_MS = 600_000
STEP_RAMP_RATIOS = (0.20, 0.40, 0.60, 0.80, 1.00)
STEP_RAMP_MIN_SECONDS = 1.0
RUSH_WARMUP_SECONDS = 3.0
RUSH_WARMUP_RATIO = 0.10
RUSH_WARMUP_MIN_VUS = 10


def _utc_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def get_os_fd_limits() -> tuple[int, int]:
    """Return (soft, hard) OS file descriptor limits, or Windows socket cap."""
    if sys.platform != "win32":
        import resource
        return resource.getrlimit(resource.RLIMIT_NOFILE)
    return WINDOWS_SOCKET_SOFT_LIMIT, WINDOWS_SOCKET_HARD_LIMIT


def get_os_fd_cap() -> int:
    """Determine the 70% OS File-Descriptor concurrency limit."""
    try:
        if sys.platform != "win32":
            import resource
            soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            rlim_inf = getattr(resource, "RLIM_INFINITY", -1)
            if soft_limit <= 0 or soft_limit == rlim_inf:
                if hard_limit > 0 and hard_limit != rlim_inf:
                    soft_limit = hard_limit
                else:
                    return MAX_REQUESTED_VUS
            return max(1, int(soft_limit * 0.70))
        return max(1, int(WINDOWS_SOCKET_SOFT_LIMIT * 0.70))
    except Exception:
        return 1024


_DEFAULT_GET_OS_FD_CAP = get_os_fd_cap


class _RollingSlice:
    __slots__ = ("slot", "max_ts", "requests", "errors", "lat_count", "hist")

    def __init__(self, slot: int, ts: float) -> None:
        self.slot = slot
        self.max_ts = ts
        self.requests = 0
        self.errors = 0
        self.lat_count = 0
        self.hist: dict[int, int] = {}


class RollingMetricsWindow:
    """1-second sliding window built from 100ms quantized histogram slices for O(1) live p95/RPS."""

    def __init__(self) -> None:
        self._slices: dict[int, _RollingSlice] = {}

    def clear(self) -> None:
        self._slices.clear()

    def _slot_for(self, ts: float) -> _RollingSlice:
        slot = math.floor(ts * 10.0)
        s = self._slices.get(slot)
        if s is None:
            s = _RollingSlice(slot, ts)
            self._slices[slot] = s
        elif ts > s.max_ts:
            s.max_ts = ts
        return s

    def prune(self, now: float) -> None:
        expired = [k for k, s in self._slices.items() if now - s.max_ts > 1.0]
        for k in expired:
            del self._slices[k]

    def record(self, ts: float, is_err: bool, latency_ms: float | None) -> None:
        self.prune(ts)
        s = self._slot_for(ts)
        s.requests += 1
        if is_err:
            s.errors += 1
        if latency_ms is not None:
            tenths = min(ROLLING_MAX_TENTHS_MS, max(0, round(latency_ms * 10.0)))
            s.hist[tenths] = s.hist.get(tenths, 0) + 1
            s.lat_count += 1

    def record_batch(
        self,
        ts: float,
        requests: int,
        errors: int,
        tenths_buckets: dict[int, int] | list[tuple[int, int]],
    ) -> None:
        self.prune(ts)
        if requests <= 0 and not tenths_buckets:
            return
        s = self._slot_for(ts)
        s.requests += requests
        s.errors += errors
        items = tenths_buckets.items() if isinstance(tenths_buckets, dict) else tenths_buckets
        for tenths, count in items:
            if count <= 0:
                continue
            key = min(ROLLING_MAX_TENTHS_MS, max(0, int(tenths)))
            s.hist[key] = s.hist.get(key, 0) + int(count)
            s.lat_count += int(count)

    def snapshot(self, now: float) -> tuple[int, float, float]:
        self.prune(now)
        if not self._slices:
            return 0, 0.0, 0.0
        total_reqs = 0
        total_errs = 0
        total_lat = 0
        merged: dict[int, int] = {}
        for s in self._slices.values():
            total_reqs += s.requests
            total_errs += s.errors
            total_lat += s.lat_count
            for k, c in s.hist.items():
                merged[k] = merged.get(k, 0) + c

        error_pct = round((total_errs / total_reqs) * 100.0, 1) if total_reqs else 0.0
        if not total_lat or not merged:
            return total_reqs, 0.0, error_pct

        rank = max(1, (total_lat * 95 + 99) // 100)
        seen = 0
        for tenths_key in sorted(merged):
            seen += merged[tenths_key]
            if seen >= rank:
                return total_reqs, round(tenths_key / 10.0, 1), error_pct
        return total_reqs, 0.0, error_pct


DISCONNECT_GRACE_SECONDS = 15.0
_ACTIVE_WS_WATCHERS: dict[str, set[int]] = {}


def compute_cdn_cache_metrics(cache_hit_count: int, total_requests: int) -> tuple[float, bool]:
    hits = max(0, int(cache_hit_count or 0))
    total = max(0, int(total_requests or 0))
    pct = round(100.0 * hits / total, 1) if total > 0 else 0.0
    warning = bool(total >= 20 and pct > 50.0)
    return pct, warning


def register_ws_watcher(owner_id: str, watcher_id: int, engines: list | tuple = ()) -> None:
    if not owner_id:
        return
    _ACTIVE_WS_WATCHERS.setdefault(owner_id, set()).add(watcher_id)
    for eng in engines:
        eng.on_ws_watcher_connected(owner_id)


def unregister_ws_watcher(owner_id: str, watcher_id: int, engines: list | tuple = ()) -> None:
    if not owner_id:
        return
    watchers = _ACTIVE_WS_WATCHERS.get(owner_id)
    if watchers is not None:
        watchers.discard(watcher_id)
        if not watchers:
            _ACTIVE_WS_WATCHERS.pop(owner_id, None)
    if not _ACTIVE_WS_WATCHERS.get(owner_id):
        for eng in engines:
            eng.on_ws_watcher_disconnected(owner_id)


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
        self.project_name: str = ""
        self._parsed_target: httpx.URL | None = None
        self.is_sandbox: bool = False
        self.cache_bust: bool = True
        self.active_guard_id: str = ""
        self.guard_expires_at: float | None = None
        self.ram_limit_mb: int = DEFAULT_RAM_CEILING_MB
        self.max_error_pct: float = DEFAULT_MAX_ERROR_PCT
        self.p95_ceiling_ms: float = 1500.0
        self.request_timeout_sec = 5.0
        self.brakes = CircuitBreakers(self.max_error_pct, self.p95_ceiling_ms)
        self.circuit_status: str = "ARMED (Normal)"
        self.same_process_loopback: bool = False
        self.advisory: str = ""
        self.loop_lag_ms: float = 0.0
        self._scaling_paused: bool = False
        self._started_at_iso: str | None = None
        self._process = psutil.Process(os.getpid())

        self.use_journey: bool = False
        self.journey_steps: list[dict] = []
        self._compiled_steps: list = []
        self._static_headers: dict[str, str] = journey_request_headers()
        self._cb_prefix: str = ""
        self._run_epoch_ms: int = 0
        self.step_metrics: list[dict] = []
        self._part_stats: dict[str, dict[str, Any]] = {}
        self.timeseries_buckets: list[dict] = []
        self._sample_interval = 1
        self._peak_rps = 0
        self._request_vus = 0
        self._peak_vus = 0

        self.connection_manager = ConnectionManager()
        self._stop_event = asyncio.Event()
        self._vu_wake_event = asyncio.Event()
        self._master_task: asyncio.Task | None = None
        self._worker_tasks: list[asyncio.Task] = []
        self._use_multiprocess: bool = False
        self._requested_multiprocess: bool | None = None
        self._worker_processes: list[mp.Process] = []
        self._worker_rss_map: dict[int, float] = {}
        self._worker_inflight_map: dict[int, int] = {}
        self._worker_loop_lag_map: dict[int, float] = {}
        self._mp_stop_event: Any = None
        self._saw_ws_watcher: bool = False
        self._last_client_keepalive_ts: float = 0.0
        self._disconnect_guard_task: asyncio.Task | None = None

        # Metrics accumulators
        self.total_requests: int = 0
        self.status_2xx: int = 0
        self.status_3xx: int = 0
        self.status_4xx: int = 0
        self.status_429: int = 0
        self.status_5xx: int = 0
        self.timeout_count: int = 0
        self.network_error_count: int = 0
        self.status_other: int = 0
        self.bytes_discarded: int = 0
        self.cache_hit_count: int = 0
        self._failed_requests = 0
        self._successful_journeys = 0
        self._latency_sample_count: int = 0
        self._latency_counts = array("Q", [0]) * (LATENCY_OVERFLOW_MS + 1)
        self._overflow_latencies: list[float] = []
        self._max_latency_ms = 0.0
        self._last_timing_check: float = 0.0

        # Rolling 1-second O(1) quantized sliding histogram window
        self._rolling_window = RollingMetricsWindow()

    def _process_ram_mb(self) -> float:
        try:
            base_rss = self._process.memory_info().rss / (1024 * 1024)
        except Exception:
            base_rss = 52.0
        return round(base_rss + sum(self._worker_rss_map.values()), 1)

    def _active_worker_pids(self) -> list[int]:
        return [proc.pid for proc in self._worker_processes if proc.pid and proc.is_alive()]

    def _ram_worker_cap(self) -> int:
        return max(1, (self.ram_limit_mb - MP_COORDINATOR_RESERVE_MB) // MP_WORKER_PROCESS_MB)

    def _should_use_multiprocess(self, requested: bool | None) -> bool:
        if (
            target_client is not _DEFAULT_TARGET_CLIENT
            or get_os_fd_cap is not _DEFAULT_GET_OS_FD_CAP
            or time is not _DEFAULT_TIME_MODULE
        ):
            return False
        if requested is not None:
            return bool(requested) and self._worker_limit >= 1
        if os.environ.get("PUSHER_DISABLE_MULTIPROCESS", "").lower() in {"1", "true", "yes"}:
            return False
        if self._ram_worker_cap() < 2:
            return False
        return self._worker_limit >= MULTIPROCESS_VU_THRESHOLD and MAX_PROCESS_WORKERS > 1

    def get_status(self, owner_id: str | None = None) -> dict:
        if owner_id is not None:
            self.touch_client_keepalive(owner_id)
        self._status_revision = max(self._status_revision + 1, monotonic_ns() // 1000)
        if owner_id is not None and owner_id != self.owner_id:
            return {
                "is_running": False, "run_id": None, "status_revision": self._status_revision,
                "project_name": "",
                "elapsed_sec": 0, "active_vus": 0, "live_rps": 0,
                "p95_ms": 0, "error_pct": 0, "use_journey": False,
                "cache_hit_count": 0, "cache_hit_pct": 0.0, "cdn_cache_warning": False,
                "step_metrics": [], "failure_breakdown": [], "crash_summary": None,
                "timeline_points": [],
                "circuit_status": "ARMED (Normal)",
                "loop_lag_ms": 0.0, "same_process_loopback": False, "advisory": "",
            }
        now = time.time()
        elapsed = int(now - self.start_time) if self.is_running else 0
        live_rps, p95_ms, error_pct = self._rolling_window.snapshot(now)

        # Current active VUs according to scheduler (bounded by spawned workers if scaling paused)
        if self.is_running:
            scheduled_vus = min(
                self._worker_limit,
                calculate_active_vus(self.traffic_mode, self.target_vus, self.duration_sec, elapsed),
            )
            active_vus = min(scheduled_vus, len(self._worker_tasks)) if self._worker_tasks else scheduled_vus
        else:
            active_vus = 0

        effective_p95 = min(float(self.p95_ceiling_ms), float(self.brakes.latency_limit))
        effective_error = min(float(self.max_error_pct), float(self.brakes.error_limit))
        failure_breakdown, crash_summary = compute_crash_diagnosis(
            self._part_stats,
            timeseries=self.timeseries_buckets,
            peak_vus=self._peak_vus,
            target_vus=self.target_vus,
            total_requests=self.total_requests,
            failed_requests=self._failed_requests,
            overall_p95_ms=p95_ms if self.is_running else self._run_p95_ms(),
            p95_ceiling_ms=effective_p95,
            circuit_status=self.circuit_status,
        )

        cache_hit_pct, cdn_cache_warning = compute_cdn_cache_metrics(
            self.cache_hit_count, self.total_requests
        )
        return {
            "is_running": self.is_running,
            "run_id": self.run_id,
            "project_name": self.project_name,
            "status_revision": self._status_revision,
            "elapsed_sec": min(elapsed, self.duration_sec),
            "duration_sec": self.duration_sec,
            "traffic_mode": self.traffic_mode,
            "active_vus": active_vus,
            "target_vus": self.target_vus,
            "peak_vus": self._peak_vus,
            "live_rps": live_rps,
            "p95_ms": p95_ms,
            "error_pct": error_pct,
            "total_requests": self.total_requests,
            "status_2xx": self.status_2xx,
            "status_3xx": self.status_3xx,
            "status_4xx": self.status_4xx,
            "status_429": self.status_429,
            "status_5xx": self.status_5xx,
            "timeout_count": self.timeout_count,
            "network_error_count": self.network_error_count,
            "status_other": self.status_other,
            "failed_requests": self._failed_requests,
            "bytes_discarded_mb": round(self.bytes_discarded / (1024 * 1024), 2),
            "cache_hit_count": self.cache_hit_count,
            "cache_hit_pct": cache_hit_pct,
            "cdn_cache_warning": cdn_cache_warning,
            "ram_mb": self._process_ram_mb(),
            "ram_limit_mb": self.ram_limit_mb,
            "p95_ceiling_ms": self.p95_ceiling_ms,
            "max_error_pct": self.max_error_pct,
            "effective_p95_ceiling_ms": effective_p95,
            "effective_max_error_pct": effective_error,
            "request_timeout_sec": self.request_timeout_sec,
            "cache_bust": self.cache_bust,
            "is_sandbox": self.is_sandbox,
            "circuit_status": self.circuit_status,
            "use_journey": self.use_journey,
            "step_metrics": self.step_metrics,
            "failure_breakdown": failure_breakdown,
            "crash_summary": crash_summary,
            "timeline_points": [
                {
                    "t": p["elapsed_sec"],
                    "vus": p["vus"],
                    "rps": p["rps"],
                    "p95_ms": p["p95_ms"],
                    "error_pct": p["error_pct"],
                }
                for p in self.timeseries_buckets[-600:]
            ],
            "loop_lag_ms": self.loop_lag_ms,
            "same_process_loopback": self.same_process_loopback,
            "advisory": self.advisory,
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
        max_error_pct: float = DEFAULT_MAX_ERROR_PCT,
        p95_ceiling_ms: float = 1500.0,
        use_journey: bool = False,
        journey_steps: list[dict] | None = None,
        is_sandbox: bool = False,
        request_timeout_sec: float = 5.0,
        guard_expires_at: float | None = None,
        same_process_loopback: bool | None = None,
        advisory: str = "",
        use_multiprocess: bool | None = None,
        project_name: str = "",
    ) -> str:
        if self.is_running or (self._master_task and not self._master_task.done()):
            raise RuntimeError("A load test is already actively running.")

        owner_id = request_owner.get()
        self.owner_id = owner_id
        self.is_sandbox = is_sandbox
        self._parsed_target = parse_target(target_url)
        self.target_url = str(self._parsed_target)
        clean_project = " ".join(str(project_name or "").split()).strip()[:80]
        if not clean_project:
            if is_sandbox:
                clean_project = "Pusher Sandbox"
            else:
                from backend.core.target_service import detect_hostname_fallback
                clean_project = detect_hostname_fallback(self.target_url)
        self.project_name = clean_project

        if same_process_loopback is None:
            from backend.core.config import settings
            from backend.core.target_policy import origin
            scheme, host, port = origin(self._parsed_target)
            self.same_process_loopback = (
                is_sandbox
                and scheme == "http"
                and host in {"127.0.0.1", "localhost", "::1"}
                and port == settings.port
                and self._parsed_target.path.startswith("/api/sandbox/")
            )
            self.advisory = (
                "Target is the in-process loopback sandbox on the same event loop; high VU counts share CPU and loop scheduling with the target."
                if self.same_process_loopback
                else ""
            )
        else:
            self.same_process_loopback = same_process_loopback
            self.advisory = advisory

        self.traffic_mode = traffic_mode
        self.target_vus = target_vus
        ram_cap = max(1, calculate_max_allowed_vus(ram_limit_mb))
        self._worker_limit = max(1, min(target_vus, ram_cap, get_os_fd_cap()))
        self._requested_multiprocess = use_multiprocess
        self._worker_rss_map = {}
        self._worker_inflight_map = {}
        self._worker_loop_lag_map = {}
        self._worker_processes = []
        self._mp_stop_event = None
        self._use_multiprocess = self._should_use_multiprocess(use_multiprocess)
        self.duration_sec = duration_sec
        self.cache_bust = cache_bust
        self.active_guard_id = active_guard_id
        self.guard_expires_at = guard_expires_at
        self.ram_limit_mb = ram_limit_mb
        self.max_error_pct = max_error_pct
        self.p95_ceiling_ms = p95_ceiling_ms
        self.request_timeout_sec = request_timeout_sec
        self.brakes = CircuitBreakers(max_error_pct, p95_ceiling_ms, target_vus=self._worker_limit)
        self.circuit_status = "ARMED (Normal)"
        self.loop_lag_ms = 0.0
        self._scaling_paused = False

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
                    "path": s.get("path", "").split("#", 1)[0].partition("?")[0],
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
        self._started_at_iso = _utc_iso(self.start_time)
        self._run_epoch_ms = int(self.start_time * 1000)
        cb_sep = "&" if "?" in self.target_url else "?"
        self._cb_prefix = f"{self.target_url}{cb_sep}_cb={self._run_epoch_ms}_"
        self._static_headers = journey_request_headers()
        self._compiled_steps = (
            [compile_journey_step(s, self._parsed_target, self.is_sandbox) for s in self.journey_steps]
            if (self.use_journey and self.journey_steps)
            else []
        )
        self.is_running = True
        self._cancel_disconnect_guard()
        self._saw_ws_watcher = bool(self.owner_id and _ACTIVE_WS_WATCHERS.get(self.owner_id))
        self._last_client_keepalive_ts = time.monotonic()

        self._stop_event = asyncio.Event()
        self.total_requests = 0
        self.status_2xx = 0
        self.status_3xx = 0
        self.status_4xx = 0
        self.status_429 = 0
        self.status_5xx = 0
        self.timeout_count = 0
        self.network_error_count = 0
        self.status_other = 0
        self.bytes_discarded = 0
        self.cache_hit_count = 0
        self._failed_requests = 0
        self._successful_journeys = 0
        self._latency_sample_count = 0
        self._latency_counts = array("Q", [0]) * (LATENCY_OVERFLOW_MS + 1)
        self._overflow_latencies = []
        self._max_latency_ms = 0.0
        self._last_timing_check = 0.0
        self._rolling_window.clear()
        self._vu_wake_event = asyncio.Event()
        self.timeseries_buckets = []
        single_path = (self._parsed_target.path or "/") if self._parsed_target else "/"
        if self.use_journey and self.journey_steps:
            self._part_stats = {
                str(idx): {
                    "part_name": s.get("name") or f"Step {idx + 1}: {s.get('method', 'GET').upper()} {s.get('path', '/')}",
                    "method": s.get("method", "GET").upper(),
                    "path": (s.get("path") or "/").split("#", 1)[0].partition("?")[0] or "/",
                    "total_requests": 0,
                    "failed_requests": 0,
                    "latency_sum": 0.0,
                    "latency_samples": 0,
                    "latency_hist": {},
                    "status_codes": {},
                    "first_error_at_sec": None,
                    "first_error_at_vus": None,
                }
                for idx, s in enumerate(self.journey_steps)
            }
        else:
            self._part_stats = {
                "0": {
                    "part_name": f"GET {single_path}",
                    "method": "GET",
                    "path": single_path,
                    "total_requests": 0,
                    "failed_requests": 0,
                    "latency_sum": 0.0,
                    "latency_samples": 0,
                    "latency_hist": {},
                    "status_codes": {},
                    "first_error_at_sec": None,
                    "first_error_at_vus": None,
                }
            }
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

    def _cancel_disconnect_guard(self) -> None:
        task = getattr(self, "_disconnect_guard_task", None)
        if task is not None and not task.done():
            task.cancel()
        self._disconnect_guard_task = None

    def touch_client_keepalive(self, owner_id: str | None) -> None:
        if self.is_running and owner_id is not None and owner_id == self.owner_id:
            self._last_client_keepalive_ts = time.monotonic()

    def on_ws_watcher_connected(self, owner_id: str) -> None:
        if not self.is_running or owner_id != self.owner_id:
            return
        self._saw_ws_watcher = True
        self._last_client_keepalive_ts = time.monotonic()
        self._cancel_disconnect_guard()

    def on_ws_watcher_disconnected(self, owner_id: str) -> None:
        if not self.is_running or owner_id != self.owner_id or not self._saw_ws_watcher:
            return
        if _ACTIVE_WS_WATCHERS.get(owner_id):
            return
        if self._disconnect_guard_task is None or self._disconnect_guard_task.done():
            try:
                self._disconnect_guard_task = asyncio.create_task(
                    self._disconnect_grace_watchdog(self.run_id or "")
                )
            except RuntimeError:
                pass

    async def _disconnect_grace_watchdog(self, watched_run_id: str) -> None:
        try:
            while (
                self.is_running
                and self.run_id == watched_run_id
                and not self._stop_event.is_set()
            ):
                if _ACTIVE_WS_WATCHERS.get(self.owner_id or ""):
                    return
                grace = max(0.05, float(DISCONNECT_GRACE_SECONDS))
                elapsed_since_keepalive = time.monotonic() - self._last_client_keepalive_ts
                remaining = grace - elapsed_since_keepalive
                if remaining <= 0:
                    self.request_stop("STOPPED (CLIENT_DISCONNECTED)")
                    return
                await asyncio.sleep(remaining)
        except asyncio.CancelledError:
            return

    async def broadcast_telemetry(self, event: str = "TICK"):
        """Broadcast live telemetry frame to all active WebSocket clients."""
        status = self.get_status()
        status["event"] = event
        await self.connection_manager.broadcast(status, self.owner_id)

    def _wake_workers(self) -> None:
        ev = getattr(self, "_vu_wake_event", None)
        if ev is not None:
            ev.set()
            self._vu_wake_event = asyncio.Event()

    def request_stop(self, status: str):
        if self.is_running and not self._stop_event.is_set():
            self.circuit_status = status
            self._stop_event.set()
            self._wake_workers()
            if self._mp_stop_event is not None:
                try:
                    self._mp_stop_event.set()
                except Exception:
                    pass

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

    def _ensure_workers(self, client: httpx.AsyncClient, worker_fn, active_target: int) -> None:
        desired = min(self._worker_limit, max(0, active_target))
        while len(self._worker_tasks) < desired and not self._stop_event.is_set():
            vu_id = len(self._worker_tasks)
            task = asyncio.create_task(worker_fn(client, vu_id))
            task.add_done_callback(self._worker_finished)
            self._worker_tasks.append(task)

    def _apply_worker_delta(self, msg: dict) -> None:
        wid = int(msg.get("worker_id", 0))
        if "rss_mb" in msg:
            self._worker_rss_map[wid] = float(msg["rss_mb"])
        if "loop_lag_ms" in msg:
            self._worker_loop_lag_map[wid] = float(msg["loop_lag_ms"])
        if "inflight" in msg:
            self._worker_inflight_map[wid] = int(msg["inflight"])

        prev_global_inflight = self._request_vus
        current_global_inflight = sum(self._worker_inflight_map.values())
        self._request_vus = current_global_inflight
        delta_peak = int(msg.get("inflight_peak", 0))
        other_inflight = max(0, current_global_inflight - self._worker_inflight_map.get(wid, 0))
        self._peak_vus = max(self._peak_vus, prev_global_inflight, current_global_inflight, other_inflight + delta_peak)

        self.status_2xx += int(msg.get("status_2xx", 0))
        self.status_3xx += int(msg.get("status_3xx", 0))
        self.status_4xx += int(msg.get("status_4xx", 0))
        self.status_429 += int(msg.get("status_429", 0))
        self.status_5xx += int(msg.get("status_5xx", 0))
        self.timeout_count += int(msg.get("timeout_count", 0))
        self.network_error_count += int(msg.get("network_error_count", 0))
        self.status_other += int(msg.get("status_other", 0))
        self.total_requests += int(msg.get("total_requests", 0))
        self._failed_requests += int(msg.get("failed_requests", 0))
        self._successful_journeys += int(msg.get("successful_journeys", 0))
        self.bytes_discarded += int(msg.get("bytes_discarded", 0))
        self.cache_hit_count += int(msg.get("cache_hit_count", 0))
        self._max_latency_ms = max(self._max_latency_ms, float(msg.get("max_latency_ms", 0.0)))

        for bucket_ms, count in msg.get("latency_buckets", ()):
            bucket = min(LATENCY_OVERFLOW_MS, max(0, int(bucket_ms)))
            c = int(count)
            self._latency_counts[bucket] += c
            self._latency_sample_count += c

        for lat in msg.get("overflow_latencies", ()):
            if len(self._overflow_latencies) < 10_000:
                self._overflow_latencies.append(float(lat))

        step_deltas = msg.get("step_deltas") or {}
        for idx, vals in step_deltas.items():
            step_idx = int(idx)
            if step_idx < len(self.step_metrics):
                sm = self.step_metrics[step_idx]
                reqs, passed, failed, lat_sum, last_status = vals
                prev_reqs = sm["requests"]
                new_reqs = prev_reqs + int(reqs)
                if new_reqs > 0:
                    sm["avg_latency_ms"] = round((sm["avg_latency_ms"] * prev_reqs + float(lat_sum)) / new_reqs, 1)
                sm["requests"] = new_reqs
                sm["passed"] += int(passed)
                sm["failed"] += int(failed)
                sm["last_status"] = int(last_status)

        part_deltas = msg.get("part_deltas") or {}
        for part_key, pdata in part_deltas.items():
            target_part = self._part_stats.get(part_key)
            if target_part is None:
                target_part = {
                    "part_name": pdata.get("part_name") or f"{pdata.get('method', 'GET')} {pdata.get('path', '/')}",
                    "method": pdata.get("method", "GET"),
                    "path": pdata.get("path", "/"),
                    "total_requests": 0,
                    "failed_requests": 0,
                    "latency_sum": 0.0,
                    "latency_samples": 0,
                    "latency_hist": {},
                    "status_codes": {},
                    "first_error_at_sec": None,
                    "first_error_at_vus": None,
                }
                self._part_stats[part_key] = target_part
            target_part["total_requests"] += int(pdata.get("total", 0))
            target_part["failed_requests"] += int(pdata.get("failed", 0))
            target_part["latency_sum"] += float(pdata.get("lat_sum", 0.0))
            target_part["latency_samples"] += int(pdata.get("lat_count", 0))
            hist = target_part["latency_hist"]
            for bucket_ms, cnt in pdata.get("buckets", ()):
                b_key = int(bucket_ms)
                hist[b_key] = hist.get(b_key, 0) + int(cnt)
            codes = target_part["status_codes"]
            for code_key, cnt in (pdata.get("codes") or {}).items():
                codes[str(code_key)] = codes.get(str(code_key), 0) + int(cnt)
            fe_sec = pdata.get("first_err_sec")
            if fe_sec is not None:
                fe_sec_i = int(fe_sec)
                fe_vus_i = int(pdata.get("first_err_vus") or 0)
                cur_sec = target_part.get("first_error_at_sec")
                if cur_sec is None or fe_sec_i < cur_sec:
                    target_part["first_error_at_sec"] = fe_sec_i
                    target_part["first_error_at_vus"] = fe_vus_i

        msg_ts = float(msg.get("ts") or time.time())
        d_total_req = int(msg.get("total_requests", 0))
        d_failed_req = int(msg.get("failed_requests", 0))
        self._rolling_window.record_batch(
            msg_ts,
            d_total_req,
            d_failed_req,
            msg.get("rolling_tenths", ()),
        )

        breaker_samples = msg.get("breaker_samples", ())
        mono_now = time.monotonic()
        for status_code, lat_ms, timed_out_int in breaker_samples:
            timed_out = bool(timed_out_int)
            if status_code != 0 or timed_out:
                self.brakes.observe_timing(mono_now, lat_ms, timed_out)
            if status_code != 403 and not timed_out:
                reason = self.brakes.observe_status(mono_now, status_code, {})
                if reason:
                    self.request_stop(f"TRIPPED ({reason})")

        if breaker_samples and len(self.brakes.timings) >= 20:
            reason = self.brakes.timing_reason(mono_now)
            if reason:
                self.request_stop(f"TRIPPED ({reason})")

        if msg.get("trip_reason"):
            self.request_stop(str(msg["trip_reason"]))

    async def _run_multiprocess_orchestrator(self) -> None:
        ram_worker_cap = self._ram_worker_cap()
        if self._requested_multiprocess is True:
            worker_count = min(MAX_PROCESS_WORKERS, max(1, min(self._worker_limit, ram_worker_cap)))
        else:
            worker_count = min(MAX_PROCESS_WORKERS, max(2, self._worker_limit // 16), ram_worker_cap)
            if worker_count <= 1:
                parsed = self._parsed_target or parse_target(self.target_url)
                timeout = httpx.Timeout(self.request_timeout_sec)
                client_cm = (
                    AiohttpLoadClient(
                        parsed, self.is_sandbox, timeout=self.request_timeout_sec, connections=self._worker_limit
                    )
                    if target_client is _DEFAULT_TARGET_CLIENT
                    else target_client(parsed, self.is_sandbox, timeout=timeout, connections=self._worker_limit)
                )
                async with client_cm as client:
                    worker = self._vu_journey_worker if self.use_journey and self.journey_steps else self._vu_worker
                    self._worker_tasks = []
                    initial_target = calculate_active_vus(
                        self.traffic_mode, self.target_vus, self.duration_sec, 0.0
                    )
                    self._ensure_workers(client, worker, initial_target)
                    monitor = asyncio.create_task(self._circuit_monitor())
                    try:
                        await self._monitor_until_stopped(client, worker)
                    finally:
                        self._stop_event.set()
                        tasks = [monitor, *self._worker_tasks]
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                        self._worker_tasks = []
                return

        ctx = mp.get_context("spawn")
        delta_queue = ctx.Queue()
        mp_stop_event = ctx.Event()
        mp_start_event = ctx.Event()
        self._mp_stop_event = mp_stop_event
        base_cap, rem_cap = divmod(self._worker_limit, worker_count)
        processes: list[mp.Process] = []
        from backend.core.config import settings as _app_settings

        for wid in range(worker_count):
            cfg = {
                "worker_id": wid,
                "worker_count": worker_count,
                "target_url": self.target_url,
                "is_sandbox": self.is_sandbox,
                "pusher_mode": _app_settings.pusher_mode,
                "sandbox_port": _app_settings.port,
                "traffic_mode": self.traffic_mode,
                "global_target_vus": self.target_vus,
                "worker_vu_cap": base_cap + (1 if wid < rem_cap else 0),
                "duration_sec": self.duration_sec,
                "start_time": self.start_time,
                "cache_bust": self.cache_bust,
                "max_error_pct": self.max_error_pct,
                "p95_ceiling_ms": self.p95_ceiling_ms,
                "request_timeout_sec": self.request_timeout_sec,
                "guard_expires_at": self.guard_expires_at,
                "use_journey": self.use_journey,
                "journey_steps": self.journey_steps,
            }
            proc = ctx.Process(
                target=run_worker_process,
                args=(cfg, delta_queue, mp_stop_event, mp_start_event),
                daemon=True,
            )
            proc.start()
            processes.append(proc)

        self._worker_processes = processes
        ready_workers: set[int] = set()
        done_workers: set[int] = set()

        def _drain_available() -> None:
            while True:
                try:
                    msg = delta_queue.get_nowait()
                except queue.Empty:
                    break
                if not isinstance(msg, dict):
                    continue
                msg_type = msg.get("type")
                if msg_type == "ready":
                    ready_workers.add(int(msg.get("worker_id", 0)))
                elif msg_type == "done":
                    wid = int(msg.get("worker_id", 0))
                    done_workers.add(wid)
                    self._worker_inflight_map[wid] = 0
                    self._request_vus = sum(self._worker_inflight_map.values())
                    if msg.get("trip_reason"):
                        self.request_stop(str(msg["trip_reason"]))
                else:
                    self._apply_worker_delta(msg)

        try:
            startup_deadline = time.monotonic() + 10.0
            while (
                not self._stop_event.is_set()
                and len(ready_workers) < worker_count
                and len(done_workers) < worker_count
                and time.monotonic() < startup_deadline
            ):
                _drain_available()
                if len(ready_workers) >= worker_count or all(not proc.is_alive() for proc in processes):
                    break
                await asyncio.sleep(0.01)

            if not self._stop_event.is_set():
                self.start_time = time.time()
            mp_start_event.set()
            last_tick = time.monotonic()

            while not self._stop_event.is_set() and len(done_workers) < worker_count:
                _drain_available()
                self.loop_lag_ms = max(self._worker_loop_lag_map.values(), default=0.0)
                if self._process_ram_mb() > self.ram_limit_mb:
                    self.request_stop(f"TRIPPED (RAM exceeds {self.ram_limit_mb} MB limit)")
                    break

                wall = time.time()
                guard_remaining = self._guard_remaining(wall)
                if guard_remaining <= 0:
                    self.request_stop("TRIPPED (Guard verification expired)")
                    break
                elapsed = wall - self.start_time
                remaining = self.duration_sec - elapsed
                if remaining <= 0:
                    break

                now = time.monotonic()
                if now - last_tick >= 1.0:
                    last_tick = now
                    snapshot = self.get_status()
                    self._sample_run(elapsed, snapshot)
                    await self.broadcast_telemetry(event="TICK")

                if all(not proc.is_alive() for proc in processes):
                    _drain_available()
                    break

                sleep_for = max(0.01, min(remaining, guard_remaining, 0.05))
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_for)
                except TimeoutError:
                    pass
        finally:
            self._stop_event.set()
            mp_stop_event.set()
            drain_deadline = time.monotonic() + 2.5
            while len(done_workers) < worker_count and time.monotonic() < drain_deadline:
                _drain_available()
                if len(done_workers) >= worker_count or all(not proc.is_alive() for proc in processes):
                    _drain_available()
                    break
                await asyncio.sleep(0.02)

            for proc in processes:
                proc.join(timeout=0.5)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=0.5)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=0.2)

            try:
                delta_queue.cancel_join_thread()
                delta_queue.close()
            except Exception:
                pass

            if self.total_requests > 0 and self._sample_interval == 1:
                final_elapsed = min(float(self.duration_sec), max(0.0, time.time() - self.start_time))
                self._sample_run(final_elapsed, self.get_status())

            self._worker_processes = []
            self._mp_stop_event = None
            self._worker_rss_map.clear()
            self._worker_inflight_map.clear()
            self._worker_loop_lag_map.clear()

    async def _run_orchestrator(self):
        timeout = httpx.Timeout(self.request_timeout_sec)
        parsed = self._parsed_target or parse_target(self.target_url)
        try:
            if self._use_multiprocess:
                await self._run_multiprocess_orchestrator()
            else:
                client_cm = (
                    AiohttpLoadClient(
                        parsed,
                        self.is_sandbox,
                        timeout=self.request_timeout_sec,
                        connections=self._worker_limit,
                    )
                    if target_client is _DEFAULT_TARGET_CLIENT
                    else target_client(
                        parsed, self.is_sandbox, timeout=timeout, connections=self._worker_limit
                    )
                )
                async with client_cm as client:
                    if not self._stop_event.is_set():
                        worker = self._vu_journey_worker if self.use_journey and self.journey_steps else self._vu_worker
                        self._worker_tasks = []
                        initial_target = calculate_active_vus(
                            self.traffic_mode, self.target_vus, self.duration_sec, 0.0
                        )
                        self._ensure_workers(client, worker, initial_target)
                        monitor = asyncio.create_task(self._circuit_monitor())
                        try:
                            await self._monitor_until_stopped(client, worker)
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

    async def _monitor_until_stopped(self, client: httpx.AsyncClient, worker_fn):
        last_tick = time.monotonic()
        high_lag_since: float | None = None
        severe_lag_since: float | None = None
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
            if not self._scaling_paused:
                desired_vus = calculate_active_vus(
                    self.traffic_mode, self.target_vus, self.duration_sec, elapsed
                )
                prev_workers = len(self._worker_tasks)
                self._ensure_workers(client, worker_fn, desired_vus)
                if desired_vus > prev_workers:
                    self._wake_workers()
            now = time.monotonic()
            if now - last_tick >= 1:
                last_tick = now
                snapshot = self.get_status()
                self._sample_run(elapsed, snapshot)
                await self.broadcast_telemetry(event="TICK")
            sleep_for = min(remaining, guard_remaining, 0.1)
            sleep_started = time.perf_counter()
            timed_out_sleep = False
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_for)
            except TimeoutError:
                timed_out_sleep = True
            if timed_out_sleep:
                perf_now = time.perf_counter()
                lag_ms = max(0.0, ((perf_now - sleep_started) - sleep_for) * 1000.0)
                self.loop_lag_ms = round(lag_ms, 1)
                if lag_ms > 200.0:
                    if high_lag_since is None:
                        high_lag_since = perf_now
                    elif perf_now - high_lag_since >= 5.0:
                        self._scaling_paused = True
                else:
                    high_lag_since = None
                    self._scaling_paused = False
                if lag_ms > 500.0:
                    if severe_lag_since is None:
                        severe_lag_since = perf_now
                    elif perf_now - severe_lag_since >= 5.0:
                        self.request_stop("TRIPPED (Host event-loop starvation)")
                        break
                else:
                    severe_lag_since = None

        if self.total_requests > 0 and self._sample_interval == 1:
            final_elapsed = min(float(self.duration_sec), max(0.0, time.time() - self.start_time))
            self._sample_run(final_elapsed, self.get_status())

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
        self._cancel_disconnect_guard()
        self._saw_ws_watcher = False
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

        end_wall = time.time()
        now_str = time.strftime("%H:%M:%S")
        started_ts = self.start_time or end_wall
        started_at = self._started_at_iso or _utc_iso(started_ts)
        ended_at_iso = _utc_iso(end_wall)
        status_snap = self.get_status()
        elapsed_float = (
            min(float(self.duration_sec), max(0.0, end_wall - self.start_time))
            if self.start_time
            else 0.0
        )
        elapsed_actual = min(int(round(elapsed_float)), self.duration_sec) if elapsed_float > 0 else 0

        effective_p95 = min(float(self.p95_ceiling_ms), float(self.brakes.latency_limit))
        effective_error = min(float(self.max_error_pct), float(self.brakes.error_limit))

        from backend.core.db_async import run_db_write
        from backend.core.report_service import detect_knee_of_curve, save_run
        knee_kwargs = {"p95_ceiling_ms": effective_p95}
        knee_sig = inspect.signature(detect_knee_of_curve).parameters
        if "max_error_pct" in knee_sig:
            knee_kwargs["max_error_pct"] = effective_error
        if "mode" in knee_sig:
            knee_kwargs["mode"] = self.traffic_mode
        knee_analysis = detect_knee_of_curve(self.timeseries_buckets, self.target_vus, **knee_kwargs)

        peak_rps_val = max(self._peak_rps, status_snap["live_rps"])
        avg_rps_val = int(round(self.total_requests / max(elapsed_float, 0.001))) if self.total_requests else 0
        run_p95_val = self._run_p95_ms()
        failure_breakdown, crash_summary = compute_crash_diagnosis(
            self._part_stats,
            timeseries=self.timeseries_buckets,
            peak_vus=self._peak_vus,
            target_vus=self.target_vus,
            total_requests=self.total_requests,
            failed_requests=self._failed_requests,
            overall_p95_ms=run_p95_val,
            p95_ceiling_ms=effective_p95,
            circuit_status=display_status,
        )

        sqlite_record = {
            "run_id": self.run_id,
            "timestamp": now_str,
            "started_at": started_at,
            "ended_at_iso": ended_at_iso,
            "target_url": self.target_url,
            "project_name": self.project_name,
            "guard_id": self.active_guard_id,
            "mode": self.traffic_mode.replace("_", " ").title(),
            "target_vus": self.target_vus,
            "peak_vus": self._peak_vus,
            "duration_sec": self.duration_sec,
            "elapsed_sec": elapsed_actual,
            "peak_rps": peak_rps_val,
            "avg_rps": avg_rps_val,
            "p95_ms": run_p95_val,
            "latency_breakdown": self.latency_breakdown(),
            "failure_breakdown": failure_breakdown,
            "crash_summary": crash_summary,
            "error_pct": round(100 * self._failed_requests / self.total_requests, 1) if self.total_requests else 0.0,
            "metrics_scope": "whole_run",
            "total_requests": self.total_requests,
            "status_2xx": self.status_2xx,
            "status_3xx": self.status_3xx,
            "status_4xx": self.status_4xx,
            "status_429": self.status_429,
            "status_5xx": self.status_5xx,
            "timeout_count": self.timeout_count,
            "network_error_count": self.network_error_count,
            "status_other": self.status_other,
            "failed_requests": self._failed_requests,
            "bytes_discarded_mb": float(status_snap.get("bytes_discarded_mb", 0.0)),
            "cache_hit_count": self.cache_hit_count,
            "cache_hit_pct": float(status_snap.get("cache_hit_pct", 0.0)),
            "cdn_cache_warning": bool(status_snap.get("cdn_cache_warning", False)),
            "ram_mb": float(status_snap.get("ram_mb", 50.0)),
            "ram_limit_mb": self.ram_limit_mb,
            "p95_ceiling_ms": self.p95_ceiling_ms,
            "max_error_pct": self.max_error_pct,
            "effective_p95_ceiling_ms": effective_p95,
            "effective_max_error_pct": effective_error,
            "request_timeout_sec": self.request_timeout_sec,
            "cache_bust": self.cache_bust,
            "use_journey": self.use_journey,
            "is_sandbox": self.is_sandbox,
            "same_process_loopback": self.same_process_loopback,
            "advisory": self.advisory,
            "verdict": verdict_cat,
            "status_label": display_status,
            "knee_vus": knee_analysis["knee_vus"],
            "knee_rps": knee_analysis["knee_rps"],
            "knee_p95_ms": knee_analysis["knee_p95_ms"],
            "bottleneck_summary": knee_analysis["bottleneck_summary"],
            "capacity_reason": knee_analysis.get("capacity_reason", ""),
            "linear_range": knee_analysis.get("linear_range", "Unavailable"),
            "optimal_point": knee_analysis.get("optimal_point", "Unavailable"),
            "cliff_point": knee_analysis.get("cliff_point", "Unavailable"),
            "steps": knee_analysis.get("steps", []),
            "capacity_checked": True,
            "timeseries": self.timeseries_buckets,
            "timeline_points": [
                {
                    "t": p["elapsed_sec"],
                    "vus": p["vus"],
                    "rps": p["rps"],
                    "p95_ms": p["p95_ms"],
                    "error_pct": p["error_pct"],
                }
                for p in self.timeseries_buckets
            ],
            "step_metrics": self.step_metrics,
        }
        await run_db_write(save_run, sqlite_record)

        await self.broadcast_telemetry(event=event_type)

    def _percentile_ms(self, pct: int) -> float | int:
        if not self._latency_sample_count:
            return 0.0
        rank = (self._latency_sample_count * pct + 99) // 100
        seen = 0
        for latency, count in enumerate(self._latency_counts):
            if not count:
                continue
            seen += count
            if seen >= rank:
                if latency == LATENCY_OVERFLOW_MS:
                    if self._overflow_latencies:
                        overflow_idx = max(0, rank - (seen - count) - 1)
                        sorted_overflow = sorted(self._overflow_latencies)
                        return round(sorted_overflow[min(overflow_idx, len(sorted_overflow) - 1)], 1)
                    return round(self._max_latency_ms, 1)
                return latency
        return 0.0

    def _run_p95_ms(self):
        return self._percentile_ms(95)

    def latency_breakdown(self) -> dict | None:
        if not self._latency_sample_count:
            return None
        return {
            "p50_ms": self._percentile_ms(50),
            "p90_ms": self._percentile_ms(90),
            "p95_ms": self._percentile_ms(95),
            "p99_ms": self._percentile_ms(99),
            "max_ms": round(self._max_latency_ms, 1),
        }

    def _request_headers(self) -> dict:
        return self._static_headers

    async def _vu_worker(self, client: httpx.AsyncClient, vu_id: int):
        req_seq = 0
        static_url = self.target_url
        cb_prefix = self._cb_prefix or f"{static_url}{'&' if '?' in static_url else '?'}_cb={int(self.start_time * 1000)}_"
        use_cb = self.cache_bust
        headers = self._request_headers()
        if self._worker_limit >= 64:
            stagger_slots = 250 if self._worker_limit >= 500 else 64
            await asyncio.sleep((vu_id % stagger_slots) * 0.004)

        while not self._stop_event.is_set():
            now = time.time()
            elapsed = now - self.start_time
            if elapsed >= self.duration_sec:
                break

            # Traffic scheduler check: suspend cleanly on _vu_wake_event when dormant
            active_target = calculate_active_vus(
                self.traffic_mode, self.target_vus, self.duration_sec, elapsed
            )
            if vu_id >= active_target:
                ev = getattr(self, "_vu_wake_event", None)
                if ev is not None:
                    await ev.wait()
                else:
                    await asyncio.sleep(0.05)
                continue

            req_seq += 1
            request_url = f"{cb_prefix}{vu_id}_{req_seq}" if use_cb else static_url

            status, received, _, latency, timed_out = await self._read_response(client, "GET", request_url, headers)
            passed = 200 <= status < 400
            self._record_response(status, received, latency, timed_out, passed)
            single_path = (self._parsed_target.path or "/") if self._parsed_target else "/"
            self._record_part(
                "0", f"GET {single_path}", "GET", single_path,
                status, latency, timed_out, not passed, elapsed, active_target,
            )

            # Small inter-request pacing so VUs generate realistic steady throughput
            await asyncio.sleep(0.01)

    async def _vu_journey_worker(self, client: httpx.AsyncClient, vu_id: int):
        req_seq = 0
        parsed_base = self._parsed_target or parse_target(self.target_url)
        compiled_steps = self._compiled_steps or [
            compile_journey_step(s, parsed_base, self.is_sandbox) for s in self.journey_steps
        ]
        epoch_ms = self._run_epoch_ms or int(self.start_time * 1000)

        while not self._stop_event.is_set():
            now = time.time()
            elapsed = now - self.start_time
            if elapsed >= self.duration_sec:
                break

            active_target = calculate_active_vus(
                self.traffic_mode, self.target_vus, self.duration_sec, elapsed
            )
            if vu_id >= active_target:
                ev = getattr(self, "_vu_wake_event", None)
                if ev is not None:
                    await ev.wait()
                else:
                    await asyncio.sleep(0.05)
                continue

            context: dict[str, str] = {}

            # Execute sequential pre-compiled steps in journey chain
            for idx, step in enumerate(compiled_steps):
                if self._stop_event.is_set():
                    break

                req_seq += 1
                try:
                    request_url, headers, body_content = step.build(
                        context, self.cache_bust, vu_id, req_seq, epoch_ms
                    )
                except JourneyInputError:
                    self.request_stop(f"FAILED (Step {idx + 1}: required journey variable unavailable)")
                    return
                except DestinationError:
                    self.request_stop("STOPPED (DESTINATION_POLICY)")
                    return

                extract_key = step.extract_key
                expected_status = step.expected_status
                status_code, received, first_chunk, req_latency, timed_out = await self._read_response(
                    client, step.method, request_url, headers,
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
                step_meta = self.journey_steps[idx] if idx < len(self.journey_steps) else {}
                raw_step_path = step_meta.get("path") or step.raw_path or "/"
                step_label = step_meta.get("name") or f"Step {idx + 1}: {step.method} {raw_step_path}"
                step_path = raw_step_path.split("#", 1)[0].partition("?")[0] or "/"
                self._record_part(
                    str(idx), step_label, step.method, step_path,
                    status_code, req_latency, timed_out, is_error, elapsed, active_target,
                    error_code_override="EXTRACTION_FAILED" if extraction_failed else None,
                )

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

    def _record_cache_hit(self) -> None:
        self.cache_hit_count += 1

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
            if isinstance(client, AiohttpLoadClient):
                status, received, preview, timed_out = await client.execute_request(
                    method,
                    url,
                    headers,
                    content=content,
                    capture=capture,
                    deadline_sec=guard_remaining,
                    brakes=self.brakes,
                    on_trip=self.request_stop,
                    on_cache_hit=self._record_cache_hit,
                )
                if timed_out and self._guard_remaining(time.time()) <= 0:
                    self.request_stop("TRIPPED (Guard verification expired)")
                    raise asyncio.CancelledError
            else:
                async with asyncio.timeout(min(self.request_timeout_sec, guard_remaining)):
                    async with client.stream(method, url, headers=headers, content=content) as response:
                        status = response.status_code
                        if AiohttpLoadClient.is_cdn_cache_hit(response.headers):
                            self._record_cache_hit()
                        if status == 403 and self.brakes.is_waf_headers(response.headers):
                            self.request_stop("TRIPPED (firewall blocked the request)")
                        else:
                            preview_tripped = False
                            async for chunk in response.aiter_bytes(chunk_size=CHUNK_SIZE_BYTES):
                                received += len(chunk)
                                if not preview and (capture or status == 403):
                                    preview = chunk
                                    if status == 403:
                                        reason = self.brakes.observe_preview(status, preview)
                                        if reason:
                                            self.request_stop(f"TRIPPED ({reason})")
                                            preview_tripped = True
                                            break
                            if not preview_tripped:
                                reason = self.brakes.observe_status(time.monotonic(), status, response.headers)
                                if reason:
                                    self.request_stop(f"TRIPPED ({reason})")
        except (httpx.TimeoutException, TimeoutError):
            if self._guard_remaining(time.time()) <= 0:
                self.request_stop("TRIPPED (Guard verification expired)")
                raise asyncio.CancelledError
            timed_out = True
            status = 0
        except httpx.RequestError:
            status = 0
            reason = self.brakes.observe_status(time.monotonic(), 0, {})
            if reason:
                self.request_stop(f"TRIPPED ({reason})")
        finally:
            self._request_vus -= 1
        return status, received, preview, (time.perf_counter() - started) * 1000, timed_out

    def _record_part(
        self,
        part_key: str,
        part_name: str,
        method: str,
        path: str,
        status_code: int,
        latency: float,
        timed_out: bool,
        is_error: bool,
        elapsed: float,
        active_vus: int,
        error_code_override: str | None = None,
    ) -> None:
        entry = self._part_stats.get(part_key)
        if entry is None:
            entry = {
                "part_name": part_name,
                "method": method,
                "path": path,
                "total_requests": 0,
                "failed_requests": 0,
                "latency_sum": 0.0,
                "latency_samples": 0,
                "latency_hist": {},
                "status_codes": {},
                "first_error_at_sec": None,
                "first_error_at_vus": None,
            }
            self._part_stats[part_key] = entry
        entry["total_requests"] += 1
        if status_code != 0 or timed_out:
            entry["latency_sum"] += latency
            entry["latency_samples"] += 1
            b = min(LATENCY_OVERFLOW_MS, max(0, math.ceil(latency)))
            hist = entry["latency_hist"]
            hist[b] = hist.get(b, 0) + 1
        if is_error:
            entry["failed_requests"] += 1
            code_key = error_code_override or classify_error_code(status_code, timed_out)
            codes = entry["status_codes"]
            codes[code_key] = codes.get(code_key, 0) + 1
            sec_i = max(0, int(elapsed))
            vu_i = max(1, int(active_vus))
            if entry["first_error_at_sec"] is None or sec_i < entry["first_error_at_sec"]:
                entry["first_error_at_sec"] = sec_i
                entry["first_error_at_vus"] = vu_i

    def _record_response(self, status, received, latency, timed_out, passed):
        if 200 <= status < 300:
            self.status_2xx += 1
        elif 300 <= status < 400:
            self.status_3xx += 1
        elif status == 429:
            self.status_429 += 1
        elif 400 <= status < 500:
            self.status_4xx += 1
        elif 500 <= status < 600:
            self.status_5xx += 1
        elif timed_out:
            self.timeout_count += 1
        elif status == 0:
            self.network_error_count += 1
        else:
            self.status_other += 1
        self.total_requests += 1
        self._failed_requests += not passed
        self.bytes_discarded += received
        now = time.time()
        valid_latency = latency if (status != 0 or timed_out) else None
        self._rolling_window.record(now, not passed, valid_latency)

        # Do not feed immediate non-timeout network failures (status == 0, timed_out=False)
        # into latency histograms or p95 windows so 1ms ConnectErrors cannot mask latency.
        if status != 0 or timed_out:
            self._latency_sample_count += 1
            bucket = min(LATENCY_OVERFLOW_MS, max(0, math.ceil(latency)))
            self._latency_counts[bucket] += 1
            if bucket == LATENCY_OVERFLOW_MS and len(self._overflow_latencies) < 10_000:
                self._overflow_latencies.append(latency)
            self._max_latency_ms = max(self._max_latency_ms, latency)

            mono_now = time.monotonic()
            self.brakes.observe_timing(mono_now, latency, timed_out)
            if len(self.brakes.timings) >= 20 and (
                timed_out
                or latency > self.brakes.latency_limit
                or mono_now - self._last_timing_check >= 0.1
            ):
                self._last_timing_check = mono_now
                reason = self.brakes.timing_reason(mono_now)
                if reason:
                    self.request_stop(f"TRIPPED ({reason})")

    async def _circuit_monitor(self):
        while not self._stop_event.is_set():
            await asyncio.sleep(0.5)
            reason = self.brakes.timing_reason(time.monotonic())
            if reason is None and self._process_ram_mb() > self.ram_limit_mb:
                reason = f"RAM exceeds {self.ram_limit_mb} MB limit"
            if reason:
                self.request_stop(f"TRIPPED ({reason})")
                break


load_engine = LoadEngine()
