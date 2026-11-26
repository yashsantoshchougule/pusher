# ISSUE-02 Execution Prompt — Fix High-VU Burst False Trips (`5 consecutive connection failures`)

- **Issue ID:** `ISSUE-02`
- **Priority:** Must Fix
- **Master Report:** [master_issue_report.md](./master_issue_report.md)

## Problem & Baseline Reproduction
At high concurrency (`1,500`–`5,000` VUs), simultaneous TCP connect bursts cause brief socket queue drops (`status == 0`) while >93% of requests succeed. `CircuitBreakers` currently aborts the entire run on `5` consecutive `status == 0` drops across all concurrent users combined, even when HTTP 5xx is 0% and rolling error ratio is healthy.

## Implementation Steps
1. **[backend/core/circuit_breakers.py](file:///c:/yash/projects/pusher/backend/core/circuit_breakers.py):**
   - Accept optional `target_vus: int = 1` in `CircuitBreakers.__init__()`.
   - Keep HTTP `5xx` consecutive threshold strictly `5` (`5 consecutive server failures`), while scaling transient `status == 0` consecutive tolerance safely at high concurrency (`5` for `target_vus < 64`, `min(40, max(10, target_vus // 40))` for `>= 64`), still guarded by rolling window ratio (`> error_limit` across `>= 20` requests).
2. **[backend/core/load_engine.py](file:///c:/yash/projects/pusher/backend/core/load_engine.py) & [backend/core/worker_process.py](file:///c:/yash/projects/pusher/backend/core/worker_process.py):**
   - Pass `target_vus=self._worker_limit` / `global_target_vus` into `CircuitBreakers`.
   - Add small initial startup micro-stagger (`min(0.25, (vu_id % 64) * 0.004)`) inside `_vu_worker` / `_vu_journey_worker` when `target_vus > 64` so all VUs do not slam Windows' TCP listen backlog in the exact same 1ms.
3. **Verify:**
   - Run `test_automatic_brakes.py` + new regression tests in `test_remediation_fixes.py` + re-run live stress tests at `500 MB / 1,500 VUs` and `1,024–2,048 MB / 2,000–5,000 VUs`.
