# SCALE-04 - Support Multiple Concurrent Runs (RunManager)

**Master Tracker:** [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md)
**Saved Plan & Prompt:** [SCALE-04-concurrent-run-manager.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/plans/SCALE-04-concurrent-run-manager.md)

---

## Issue
- **ID & Priority:** `SCALE-04` — `Must Fix`
- **Symptom & Impact:** `LoadEngine` was a global server-wide singleton, blocking a second authenticated operator from launching a test while another operator's run was active.

## How It Occurred
`backend/api/load_router.py`, `target_router.py`, `target_service.py`, and `main.py` referenced a single module-level `load_engine` instance without per-run/per-owner engine allocation or shared host VU quota accounting.

## How It Was Solved
- **[NEW] [run_manager.py](file:///c:/yash/projects/pusher/backend/core/run_manager.py)**: Added `RunManager(load_engine)` maintaining `_runs` by `run_id`, `_owner_latest` per operator, `total_reserved_vus()` host-wide FD quota enforcement, `acquire_engine_for_start()` (sharing `ConnectionManager` across isolated engines), `find_by_run_id()`, `stop_guard_runs()`, and `stop_all()`.
- **[MODIFY] [load_router.py](file:///c:/yash/projects/pusher/backend/api/load_router.py)**: Routed `/api/load/start`, `/api/load/stop`, `/api/load/status` (`?run_id=`), `/api/load/simulate-spike` (`?run_id=`), and `/api/load/ws` through `run_manager` while keeping full compatibility with legacy `load_engine` monkeypatches.
- **[MODIFY] [target_router.py](file:///c:/yash/projects/pusher/backend/api/target_router.py)**, **[target_service.py](file:///c:/yash/projects/pusher/backend/core/target_service.py)**, **[main.py](file:///c:/yash/projects/pusher/backend/main.py)** & **[conftest.py](file:///c:/yash/projects/pusher/supporting%20files/testing/conftest.py)**: Connected guard revocation/device-violation/lifespan shutdown hooks and legacy test fixture resets to `run_manager`.

## Testing
- **New & Operator Isolation Tests (`test_concurrent_runs.py`, `test_operator_access.py`):** **`6 passed in 1.14s`** (proving simultaneous execution by `alice` and `bob`, duplicate-user `409`, global FD quota `409`, cross-owner stop `403`, and stopping `alice` while keeping `bob` alive).
- **Full Python Suite:** `py -m pytest "supporting files/testing/unit" -q --tb=short`: **`212 passed, 40 warnings in 29.26s`** (exit `0`).
- **Flask Guard Check:** `py "supporting files/testing/verification/check_flask_guard.py"` — passed (exit `0`).

## Result
- **Status:** `Resolved`
- Passed all `SCALE-04` acceptance criteria; cleared to advance to `SCALE-05`.
