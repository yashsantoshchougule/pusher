# SCALE-01 - Multi-Process Worker Pool & Production Entrypoint Separation

**Master Tracker:** [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md)
**Saved Plan & Prompt:** [SCALE-01-multi-process-worker-pool.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/plans/SCALE-01-multi-process-worker-pool.md)

---

## Issue
- **ID & Priority:** `SCALE-01` — `Must Fix`
- **Symptom & Impact:** `LoadEngine` ran all virtual users on one `asyncio` event loop inside the FastAPI/Uvicorn web process (`reload=True`), limiting HTTP traffic generation to 1 CPU core and inflating `p95_ms` whenever coordinator I/O or event-loop work grew.

## How It Occurred
1. `LoadEngine._run_orchestrator()` spawned all HTTP VU coroutines on the main API event loop.
2. `backend/main.py` hardcoded `reload=True` when launched directly (`__main__`) and needed clean shutdown termination for worker processes.

## How It Was Solved
- **[NEW] [worker_process.py](file:///c:/yash/projects/pusher/backend/core/worker_process.py)**: Added a Windows `spawn`-safe standalone worker entrypoint (`run_worker_process`, `_ProcessWorkerRunner`, `worker_active_target`) running isolated `asyncio` loops + `target_client` pools, propagating `settings.pusher_mode` / `settings.port`, synchronizing start via `mp_start_event`, running fast local breakers (`429`, WAF `403`, `5xx`, timing), and emitting incremental `0.2s` IPC deltas (`delta_queue`).
- **[MODIFY] [load_engine.py](file:///c:/yash/projects/pusher/backend/core/load_engine.py)**: Added `_should_use_multiprocess()`, `_run_multiprocess_orchestrator()`, `_apply_worker_delta()`, coordinate-level aggregate breaker/RAM tracking (`_process_ram_mb()`), guaranteed child termination/reaping on `stop()`/`simulate_spike()`/trip/completion, and automatic in-process fallback when unit tests monkeypatch `target_client`, `get_os_fd_cap`, or `time`.
- **[MODIFY] [main.py](file:///c:/yash/projects/pusher/backend/main.py)**: Verified clean FastAPI `lifespan` engine shutdown hook and gated `reload` behind `PUSHER_DEV_RELOAD=1`.

## Testing
- **New Unit Tests:** `py -m pytest "supporting files/testing/unit/test_multiprocess_engine.py" -v`
  - **Result:** `4 passed in 11.14s` (covering exact global VU sum sharding, monkeypatch fallback, Step-Ramp completion & process reaping, and `MANUAL_ABORT` + `503` `CIRCUIT_BREAKER` termination with `0` leaked child PIDs).
- **Full Python Suite:** `py -m pytest "supporting files/testing/unit" -q --tb=short`
  - **Result:** `204 passed, 30 warnings in 32.40s` (exit `0`).
- **Sandbox Security Check:** `py "supporting files/testing/verification/check_local_sandbox.py"`
  - **Result:** `Offline sandbox smoke check passed.` (exit `0`).
- **Throughput Benchmark:** `py "supporting files/testing/verification/bench_scale01_multiprocess.py"` (`64` VUs, `3s` duration against local `ThreadingHTTPServer`):
  - `single_process`: `632` requests in `3.07s` — `206.1 RPS`, `p95_ms = 474`
  - `multi_process`: `4,599` requests (`4,577` 2xx) in `5.71s` wall — `806.1 RPS` (`3.9x` wall RPS / `7.3x` request volume), `p95_ms = 15` (`31x` latency reduction)

## Result
- **Status:** `Resolved`
- All `SCALE-01` acceptance criteria passed; cleared to advance to `SCALE-02`.
