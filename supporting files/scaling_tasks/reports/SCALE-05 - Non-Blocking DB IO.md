# SCALE-05 - Non-Blocking Database I/O & Async Write Offload

**Master Tracker:** [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md)
**Saved Plan & Prompt:** [SCALE-05-non-blocking-db-io.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/plans/SCALE-05-non-blocking-db-io.md)

---

## Issue
- **ID & Priority:** `SCALE-05` — `Should Fix`
- **Symptom & Impact:** Synchronous `sqlite3` reads and writes in `LoadEngine._finish_run()` (`save_run`) and FastAPI async routes blocked the main asyncio event loop during run persistence and archive queries.

## How It Occurred
`report_router.py`, `profile_router.py`, `load_router.py`, `journey_router.py`, and `LoadEngine._finish_run()` called synchronous SQLite functions directly on the FastAPI event-loop thread.

## How It Was Solved
- **[NEW] [db_async.py](file:///c:/yash/projects/pusher/backend/core/db_async.py)**: Implemented `run_db_read()` (`asyncio.to_thread`) and `run_db_write()` (serialized onto a single daemon `ThreadPoolExecutor(max_workers=1)` with `contextvars.copy_context()` so `request_owner` ContextVar propagates faithfully without SQLite writer lock contention).
- **[MODIFY] [load_engine.py](file:///c:/yash/projects/pusher/backend/core/load_engine.py)**: Awaits `run_db_write(save_run, sqlite_record)` inside `_finish_run()`.
- **[MODIFY] [report_router.py](file:///c:/yash/projects/pusher/backend/api/report_router.py)**, **[profile_router.py](file:///c:/yash/projects/pusher/backend/api/profile_router.py)**, **[load_router.py](file:///c:/yash/projects/pusher/backend/api/load_router.py)**, **[journey_router.py](file:///c:/yash/projects/pusher/backend/api/journey_router.py)**: Offloaded SQLite read and write endpoints to `run_db_read` / `run_db_write` while keeping synchronous helpers in `database.py` and `report_service.py` 100% compatible with existing sync tests.

## Testing
- **Targeted Tests (`test_async_db_offload.py`, `test_database_persistence.py`, `test_stage5_reports_history.py`):** **`19 passed in 1.97s`** (verifying concurrent event-loop ticker ticks unblocked during slow writes, strict single-writer thread serialization, and `request_owner` ContextVar propagation).
- **Full Python Suite:** `py -m pytest "supporting files/testing/unit" -q --tb=short`: **`214 passed, 40 warnings in 26.11s`** (exit `0`).

## Result
- **Status:** `Resolved`
- Passed all `SCALE-05` acceptance criteria; cleared to advance to `SCALE-06`.
