# `SCALE-03` Plan & Detailed Execution Prompt

- **Issue ID:** `SCALE-03` (Position 3 of 6 in [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md))
- **Exact Title:** Eliminate Idle Worker Polling & O(N log N) Per-Tick Latency Sorting
- **Priority:** `Must Fix`

---

## 1. Problem, Baseline & Confirmed Cause
- **Current bottlenecks:**
  1. `_vu_worker` and `_vu_journey_worker` in `backend/core/load_engine.py` and `backend/core/worker_process.py` execute `await asyncio.sleep(0.08)` when `vu_id >= active_target`, generating periodic wakeups on idle tasks.
  2. `LoadEngine._rolling_latencies` and `_rolling_requests` store every individual request tuple over the last 1.0s; `get_status()` copies and runs `sorted(lat for _, lat in self._rolling_latencies)` on every poll/WebSocket frame ($O(N \log N)$), and multi-process workers ship every raw per-request sample tuple (`_d_samples`) over `multiprocessing.Queue`!
  3. Because `aiohttp` easily drives `2,100+ RPS` in 1 process, `MULTIPROCESS_VU_THRESHOLD = 16` triggered `spawn` overhead prematurely at moderate concurrency (`64` VUs).
- **Expected behavior & Acceptance Criteria:**
  1. Replace `asyncio.sleep(0.08)` busy-polling with an `asyncio.Condition` (`_vu_gate`) signaled cleanly whenever active target VUs step up or stop triggers (`0` wakeups while dormant).
  2. Replace raw `_rolling_latencies` / `_rolling_requests` per-request list sorting with a compact `RollingMetricsWindow` using `100ms` sub-second ring slices + histogram buckets:
     - $O(1)$ per `_record_response()` recording (no deque float sorting in `get_status()`!).
     - Preserves exact fractional `p95_ms` precision on light traffic and millisecond/sub-ms nearest-rank accuracy on high traffic (`test_whole_run_metrics.py:25-26` `5`, `test_telemetry`, etc.).
  3. Shrink multi-process IPC `delta_queue` messages from N raw `samples` tuples down to pre-aggregated slice/bucket summaries (`rolling_bucket_deltas`, `rolling_req_delta`, `rolling_err_delta`), keeping global `CircuitBreakers` status/timing observation accurate at high RPS.
  4. Tune `MULTIPROCESS_VU_THRESHOLD = 128` (while respecting explicit `use_multiprocess=True/False`) so small-to-medium `aiohttp` runs avoid process spawn latency while heavy runs (`>= 128` VUs) scale across cores cleanly.

---

## 2. Affected Files
- `[MODIFY]` `backend/core/load_engine.py` — add `RollingMetricsWindow`, replace `_rolling_latencies`/`_rolling_requests` sorting in `get_status()`, replace `0.08s` idle sleep with `_vu_gate` Condition, ingest compact IPC bucket deltas in `_apply_worker_delta()`, tune `MULTIPROCESS_VU_THRESHOLD = 128`.
- `[MODIFY]` `backend/core/worker_process.py` — replace `0.08s` idle sleep with `_vu_gate` Condition and replace unbounded `_d_samples` raw per-request tuple list with bounded breaker samples / compact aggregated counts + histogram deltas.
- `[NEW]` `supporting files/testing/unit/test_rolling_window_and_wakeup.py` — test $O(1)$ rolling window accuracy, 1s slice expiry, high-volume (`20,000` sample) `get_status()` speed (`< 2ms`), and zero-poll dormant worker Condition wakeup.

---

## 3. Detailed Execution Prompt (Issue 3 — `SCALE-03`)

> **Task:** Implement `SCALE-03` cleanly across `backend/core/load_engine.py` and `backend/core/worker_process.py`.
>
> **Exact Steps to Execute:**
> 1. **Add `RollingMetricsWindow` in `backend/core/load_engine.py`:**
>    - Store up to 12 `100ms` sub-second slices (`bucket_id = int(now * 10)`), expiring slices where `now - slice_ts > 1.0`.
>    - Each slice tracks `requests: int`, `errors: int`, `bytes_total: int`, and quantized `latency_hist: defaultdict[int, int]` (storing `int(round(latency_ms * 10))` tenth-ms precision up to `600_000`, giving exact `0.1ms` precision AND constant-time nearest-rank `p95()` across the `<= 11` active slices by sorting ONLY unique distinct quantized buckets rather than `N` request floats!).
>    - Update `LoadEngine.get_status()`, `_record_response()`, and `_apply_worker_delta()` to use `RollingMetricsWindow` (no full `N`-item `sorted()`!).
> 2. **Eliminate `0.08s` idle sleep polling in `load_engine.py` and `worker_process.py`:**
>    - Add `asyncio.Condition()` (`_vu_gate`) on `LoadEngine` and `_ProcessWorkerRunner`.
>    - Instead of `await asyncio.sleep(0.08)`, inactive VUs wait inside `async with _vu_gate: await _vu_gate.wait()` until `active_target` changes or stop is requested, notified in `_monitor_until_stopped` / `request_stop` / worker loop!
> 3. **Shrink Worker IPC Delta Payloads & Tune Threshold:**
>    - In `worker_process.py`, stop appending every single request tuple into `_d_samples` unconditionally at multi-thousand RPS; instead emit compact aggregate counts + sparse `latency_buckets` + `rolling_buckets` (tenth-ms buckets) and capped breaker samples/status summaries (`<= 64` representative items or counts) so queue pickling stays tiny even at `10,000+ RPS`.
>    - Update `MULTIPROCESS_VU_THRESHOLD = 128`.
> 4. **Write & Run Verification (`SCALE-03` Gate):**
>    - Create `supporting files/testing/unit/test_rolling_window_and_wakeup.py` covering rolling expiry, fractional `p95` accuracy, 20k-sample constant-time `get_status()`, and Condition wakeup behavior.
>    - Run `py -m pytest "supporting files/testing/unit" -q --tb=short` and verify all tests pass, then save `supporting files/scaling_tasks/reports/SCALE-03 - Zero-Poll and O1 Buckets.md`.
