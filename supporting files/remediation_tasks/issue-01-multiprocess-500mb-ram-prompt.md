# ISSUE-01 Execution Prompt — Fix Default `500 MB` Multi-Process RAM Premature Crash

- **Issue ID:** `ISSUE-01`
- **Priority:** Must Fix (Critical Crash)
- **Master Report:** [master_issue_report.md](./master_issue_report.md)

## Problem & Baseline Reproduction
Under Pusher's default `500 MB` RAM preset with `>= 128 VUs` (`500` VUs `steady_crowd` and `1,500` VUs `step_ramp`), `LoadEngine._run_multiprocess_orchestrator()` computes `ram_worker_cap = max(1, (self.ram_limit_mb - 90) // 55)` (`7` spawned workers). On Windows `spawn`, each worker uses ~65–72 MB RSS plus ~80 MB coordinator RSS = **~554–557 MB** immediately at startup, triggering `TRIPPED (RAM exceeds 500 MB limit)` before traffic ramps cleanly.

## Implementation Steps
1. **[backend/core/load_engine.py](file:///c:/yash/projects/pusher/backend/core/load_engine.py):**
   - Introduce realistic Windows/spawn process overhead constants: `MP_COORDINATOR_RESERVE_MB = 120` and `MP_WORKER_PROCESS_MB = 85`.
   - Compute `ram_worker_cap = max(1, (self.ram_limit_mb - MP_COORDINATOR_RESERVE_MB) // MP_WORKER_PROCESS_MB)`:
     - `250 MB` -> `1` worker (runs cleanly in single-process `AiohttpLoadClient` mode under ~110 MB total RSS).
     - `500 MB` -> `4` workers max (`~340–410 MB` total RSS, safely under `500 MB`).
     - `1,024+ MB` -> up to `MAX_PROCESS_WORKERS` (<= 8 workers).
   - Ensure `_should_use_multiprocess(None)` stays single-process when `ram_worker_cap <= 1`, and ensure the single-process fallback inside `_run_multiprocess_orchestrator` uses `AiohttpLoadClient` when `target_client is _DEFAULT_TARGET_CLIENT` instead of slow `httpx`.
2. **Verify:**
   - Re-run live RAM stress tiers (`250 MB / 200 VUs`, `500 MB / 500 VUs`, `500 MB / 1,500 VUs`) and confirm `status = 'ARMED (Normal)'` and `peak_ram < ram_limit_mb`.
   - Add regression tests in `supporting files/testing/unit/test_remediation_fixes.py` and run `test_multiprocess_engine.py` + `test_remediation_fixes.py`.
