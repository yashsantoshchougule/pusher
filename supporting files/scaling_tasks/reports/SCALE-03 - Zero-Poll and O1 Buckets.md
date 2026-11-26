# SCALE-03 - Eliminate Idle Worker Polling & O(N log N) Per-Tick Latency Sorting

**Master Tracker:** [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md)
**Saved Plan & Prompt:** [SCALE-03-zero-poll-and-o1-buckets.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/plans/SCALE-03-zero-poll-and-o1-buckets.md)

---

## Issue
- **ID & Priority:** `SCALE-03` — `Must Fix`
- **Symptom & Impact:** Dormant VUs woke every `80ms` (`asyncio.sleep(0.08)`), `get_status()` ran `sorted()` over the entire 1-second `_rolling_latencies` deque on every status poll/WS tick, multi-process workers shipped uncompressed per-request sample lists across `multiprocessing.Queue`, and `MULTIPROCESS_VU_THRESHOLD = 16` spawned sub-processes prematurely for moderate `aiohttp` loads.

## How It Occurred
1. `_vu_worker` and `_vu_journey_worker` in `load_engine.py` and `worker_process.py` slept `0.08s` when `vu_id >= active_target`.
2. `_rolling_latencies` and `_rolling_requests` deques stored raw tuples sorted linearly inside `get_status()`.
3. `_ProcessWorkerRunner` appended every single response 5-tuple into `_d_samples`.

## How It Was Solved
- **[MODIFY] [load_engine.py](file:///c:/yash/projects/pusher/backend/core/load_engine.py)**:
  - Added `_RollingSlice` and `RollingMetricsWindow` (`100ms` quantized sub-second histogram slices storing tenth-ms buckets), making `_record_response()`, `_apply_worker_delta()`, and `get_status()` nearest-rank `p95_ms`/`live_rps`/`error_pct` independent of total raw sample count $N$.
  - Added lock-free `_vu_wake_event` (`asyncio.Event` swapped via `_wake_workers()`) so dormant VUs consume 0 wakeups until step-up or stop.
  - Tuned `MULTIPROCESS_VU_THRESHOLD = 128`.
- **[MODIFY] [worker_process.py](file:///c:/yash/projects/pusher/backend/core/worker_process.py)**:
  - Replaced `0.08s` idle polling with `_vu_wake_event.wait()`.
  - Replaced unbounded `_d_samples` IPC payload with compact quantized `rolling_tenths` counts + bounded `breaker_samples` (`<= 64`).

## Testing
- **Targeted Tests (`test_rolling_window_and_wakeup.py`, `test_whole_run_metrics.py`, `test_multiprocess_engine.py`):** **`11 passed in 9.28s`** (verifying quantile accuracy, 1s slice expiry, 20,000-sample `snapshot()` speed under 25ms, and zero-poll dormant wakeups).
- **Full Python Suite:** `py -m pytest "supporting files/testing/unit" -q --tb=short`: **`211 passed, 30 warnings in 24.17s`** (exit `0`).
- **Sandbox Check:** `py "supporting files/testing/verification/check_local_sandbox.py"` — passed (exit `0`).

## Result
- **Status:** `Resolved`
- Passed all `SCALE-03` acceptance criteria; cleared to advance to `SCALE-04`.
