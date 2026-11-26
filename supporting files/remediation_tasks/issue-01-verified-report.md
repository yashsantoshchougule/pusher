# ISSUE-01 Verified Report — Fix Default `500 MB` Multi-Process RAM Premature Crash

- **Issue ID:** `ISSUE-01`
- **Priority:** Must Fix
- **Result:** `Resolved`
- **Plan Link:** [issue-01-multiprocess-500mb-ram-prompt.md](./issue-01-multiprocess-500mb-ram-prompt.md)

## How It Occurred
`LoadEngine._run_multiprocess_orchestrator()` previously estimated worker RAM at `55 MB` and coordinator reserve at `90 MB` (`(500 - 90) // 55 = 7` workers), causing `~556 MB` RSS on Windows at startup and immediately tripping `TRIPPED (RAM exceeds 500 MB limit)`.

## How It Was Solved
- Updated [load_engine.py](file:///c:/yash/projects/pusher/backend/core/load_engine.py) with `MP_COORDINATOR_RESERVE_MB = 120` and `MP_WORKER_PROCESS_MB = 85` (`_ram_worker_cap()`), keeping `500 MB` at `<= 4` workers and routing `250 MB` cleanly via single-process `AiohttpLoadClient`.

## Testing Evidence
- `py -m pytest "supporting files/testing/unit/test_remediation_fixes.py" "supporting files/testing/unit/test_multiprocess_engine.py" -q` -> **6 passed**.
- Live stress test (`audit_ram_tiers.py`):
  - `250 MB / 200 VUs` -> `ARMED (Normal)`, `peak_ram = 154.8 MB`, `16,339` reqs, `0` failed.
  - `500 MB / 500 VUs` -> `ARMED (Normal)`, `peak_ram = 383.6 MB`, `26,085` reqs, `0` failed.
  - `500 MB / 1,500 VUs` -> `peak_ram = 384.1 MB` (< 500 MB; zero RAM trip).
