# `SCALE-01` Plan & Detailed Execution Prompt

- **Issue ID:** `SCALE-01` (Position 1 of 6 in [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md))
- **Exact Title:** Multi-Process Worker Pool & Production Entrypoint Separation
- **Priority:** `Must Fix`

---

## 1. Problem, Baseline & Confirmed Cause
- **Current bottleneck:** `LoadEngine` in `backend/core/load_engine.py` executes every virtual user (`_vu_worker` / `_vu_journey_worker`) on the single FastAPI/Uvicorn `asyncio` event loop. Meanwhile `backend/main.py:97` hardcodes `uvicorn.run("backend.main:app", ..., reload=True)`.
- **Visible impact:**
  1. Only **1 CPU core** generates HTTP load regardless of host core count (`os.cpu_count()`).
  2. API requests, WebSockets, SQLite writes, and in-process `/api/sandbox/target` fight for the exact same Python GIL/event-loop thread as the load generator.
  3. Launching `python -m backend.main` always boots a file-watching reloader process rather than a clean production worker host.
- **Expected behavior & Acceptance Criteria:**
  1. Real load runs above the multi-process threshold (`>= 16` workers by default, or explicit `use_multiprocess=True`) automatically shard `target_vus` across $N \le \text{cpu\_count}$ OS worker processes (`multiprocessing.get_context("spawn")`) via a dedicated `backend/core/worker_process.py` runner.
  2. Each worker slices `base_vus + (1 if idx < rem else 0)`, keeps proportional Step-Ramp / Sudden-Rush / Steady-Crowd concurrency curves (`calculate_active_vus` preserves aggregate total VUs per second!), evaluates fast local safety breakers (`429`, WAF `403`, `5xx`, p95/timeout, RAM), and streams compact delta payloads over `multiprocessing.Queue` (~`0.2s` flush interval + terminal flush) to the `LoadEngine` coordinator.
  3. Coordinator aggregates worker deltas into live `get_status()`, WebSocket frames, `timeseries_buckets`, `step_metrics`, `latency_breakdown()`, `bytes_discarded`, and `save_run()` seamlessly, summing RSS across coordinator + active worker PIDs.
  4. Stopping (`/api/load/stop`), circuit tripping, guard expiry, simulate-spike, or server shutdown cleanly shuts down and reaps **all** child worker processes with zero orphan processes left alive.
  5. When `engine_module.target_client` is monkeypatched in unit tests (or small local runs `< 16` VUs without explicit `use_multiprocess=True`), `LoadEngine` seamlessly runs its in-process async mode so all existing `200` unit tests continue to pass untouched.
  6. `backend/main.py` disables `reload=True` unless `PUSHER_DEV_RELOAD=1` is set and attaches a FastAPI `lifespan` handler that calls `await load_engine.stop("ENGINE_SHUTDOWN")` if active.

---

## 2. Affected Files
- `[NEW]` `backend/core/worker_process.py` — `spawn`-safe worker process main loop, chunked delta IPC emitter, per-worker control queue listener (`stop` / `spike`), RSS measurement, and local safety checks.
- `[MODIFY]` `backend/core/load_engine.py` — track `_DEFAULT_TARGET_CLIENT`, add `_should_use_multiprocess()`, shard VUs across `spawn` workers, ingest worker delta messages into existing accumulators (`_latency_counts`, `status_*`, `timeout_count`, `network_error_count`, `_rolling_*`, `step_metrics`, `_peak_vus`), manage worker termination & RSS sum.
- `[MODIFY]` `backend/main.py` — replace hardcoded `reload=True` with env-gated dev reload + clean FastAPI `lifespan` shutdown cleanup.
- `[NEW]` `supporting files/testing/unit/test_multiprocess_engine.py` — tests covering multi-worker Step-Ramp / Steady-Crowd slice aggregation, `simulate_spike()` / `stop()` clean process reaping (`0` leaked PIDs), multi-worker `CIRCUIT_BREAKER` propagation, and fallback in-process parity.
- `[NEW]` `supporting files/testing/verification/bench_scale01_multiprocess.py` — loopback multi-process vs single-process throughput/RPS benchmark against an independent HTTP target server.

---

## 3. Detailed Execution Prompt (Issue 1 — `SCALE-01`)

> **Task:** Implement `SCALE-01` (Multi-Process Worker Pool & Production Entrypoint Separation) cleanly on Pusher without breaking any existing unit tests or API contracts.
>
> **Exact Steps to Execute:**
> 1. **Create `backend/core/worker_process.py`:**
>    - Define a top-level pickleable worker entrypoint `run_worker_process(config: dict, delta_queue, stop_event)` runnable under Windows `multiprocessing.get_context("spawn")`.
>    - Inside the worker process, bootstrap a fresh `asyncio` event loop and run async `LoadWorker` logic reusing `calculate_active_vus`, `target_client`, `CircuitBreakers`, `append_cache_buster`, `build_journey_request`, `extract_journey_value`, and `CHUNK_SIZE_BYTES`.
>    - Shard VUs cleanly: slice `(worker_vus, worker_ram_limit_mb, worker_id, num_workers)`. Note: pass `start_time` from coordinator so Step-Ramp step transitions (`t=0..duration`) synchronize tightly across all worker processes.
>    - Accumulate per-interval delta metrics inside the worker (`requests`, `status_2xx`, `status_3xx`, `status_4xx`, `status_429`, `status_5xx`, `timeout_count`, `network_error_count`, `status_other`, `failed_requests`, `bytes_discarded`, sparse latency histogram dict `{bucket_ms: count}`, `overflow_latencies`, `rolling_latencies` list `[float]`, `rolling_errors` int, `inflight_peak`, `loop_lag_ms`, optional `step_deltas` for journey mode, `worker_rss_mb`, `trip_reason`).
>    - Every `0.2s` (and immediately on loop exit or trip), flush non-empty delta dict to `delta_queue` and reset interval deltas. If `stop_event.is_set()` or `trip_reason` triggers, cancel active tasks cleanly, flush final delta + `{"event": "WORKER_DONE", "worker_id": ..., "trip_reason": ...}`, close client, and exit promptly.
> 2. **Upgrade `backend/core/load_engine.py`:**
>    - Capture `_DEFAULT_TARGET_CLIENT = target_client` at import time.
>    - Add optional parameter `use_multiprocess: bool | None = None` to `LoadEngine.start(...)` (keeping all existing positional/keyword defaults 100% compatible).
>    - Add `MAX_PROCESS_WORKERS = min(8, os.cpu_count() or 1)` and `MULTIPROCESS_VU_THRESHOLD = 16`.
>    - `_should_use_multiprocess(requested)`: return `False` if `target_client is not _DEFAULT_TARGET_CLIENT` (so monkeypatched mock tests run fast in-process), else return `bool(requested)` if explicitly provided, else return `self._worker_limit >= MULTIPROCESS_VU_THRESHOLD and MAX_PROCESS_WORKERS > 1`.
>    - When in multi-process mode:
>      - Compute `num_procs = min(MAX_PROCESS_WORKERS, max(1, self._worker_limit // 4))` (or `min(MAX_PROCESS_WORKERS, self._worker_limit)` when explicitly forced), split `self._worker_limit` evenly (`base, rem = divmod(self._worker_limit, num_procs)`).
>      - Spawn processes via `mp.get_context("spawn")`, allocate shared `mp_stop_event = ctx.Event()` and `delta_queue = ctx.Queue()`.
>      - Run an async `_drain_worker_deltas(...)` reader inside `_run_orchestrator()` that drains `delta_queue` (non-blocking `get_nowait` + short await/sleep), folds every worker delta into `LoadEngine` accumulators (`status_*`, `_latency_counts`, `_rolling_requests`, `_rolling_latencies`, `step_metrics`, `_peak_vus = max(...)`, `self._worker_rss_map[wid]`), evaluates aggregate `CircuitBreakers` / aggregate RAM (`coordinator RSS + sum(worker RSS) > self.ram_limit_mb`), and triggers `request_stop(...)` + `mp_stop_event.set()` if tripped or manually stopped.
>      - On exit/cancel/finally, set `mp_stop_event`, join processes cleanly (`timeout=2.0`), then `.terminate()` / `.kill()` any stragglers and close queue (`close()` + `join_thread()` / `cancel_join_thread()`), asserting zero lingering workers.
>      - Override `_process_ram_mb()` to return `round(coordinator_rss + sum(worker_rss.values()), 1)`.
> 3. **Update `backend/main.py`:**
>    - Replace `@app` without lifespan with a FastAPI `lifespan` context manager that stops `load_engine` on app shutdown.
>    - Guard `reload=os.environ.get("PUSHER_DEV_RELOAD", "0") == "1"` in `uvicorn.run(...)` (default `False` for clean production startup).
> 4. **Write Tests & Benchmark:**
>    - Create `supporting files/testing/unit/test_multiprocess_engine.py`: test multi-process worker spawning (`use_multiprocess=True`) against a local `ThreadingHTTPServer`, verify total requests + status breakdowns + histogram latency + `peak_vus`, test `stop()` / `CIRCUIT_BREAKER` / `simulate_spike()` cleanly reaps every child PID (`process.is_alive() is False`), and test `_should_use_multiprocess()` falls back cleanly when `target_client` is monkeypatched.
>    - Create `supporting files/testing/verification/bench_scale01_multiprocess.py` comparing single-process vs multi-process loopback throughput & RPS against a separate-process HTTP target.
> 5. **Verify Gate:** Run pytest on `test_multiprocess_engine.py` + full `supporting files/testing/unit/` (`py -m pytest ...`) + `check_local_sandbox.py` + `bench_scale01_multiprocess.py`, then record the verified report at `supporting files/scaling_tasks/reports/SCALE-01 - Multi-Process Worker Pool.md`.

---

## 4. Rollback Plan
- Set `PUSHER_DISABLE_MULTIPROCESS=1` or default `use_multiprocess=False` inside `LoadEngine.start()` to immediately revert traffic execution to single-process async mode without changing any API schema or SQLite structure.
