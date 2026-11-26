# `SCALE-05` Plan & Detailed Execution Prompt

- **Issue ID:** `SCALE-05` (Position 5 of 6 in [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md))
- **Exact Title:** Non-Blocking Database I/O & Async Write Offload
- **Priority:** `Should Fix`

---

## 1. Problem, Baseline & Confirmed Cause
- **Current bottleneck:** `LoadEngine._finish_run()` (`save_run(...)`) and async FastAPI routes (`profile_router.py`, `report_router.py`, `load_router.py`, `journey_router.py`) invoke synchronous `sqlite3` calls directly on the asyncio event loop thread.
- **Visible impact:** Under concurrent load tests (`SCALE-04`), WAL checkpoints, `save_run()` inserts with large timeseries JSON, or `/api/history` archive queries block WebSocket heartbeats and HTTP handlers on the FastAPI event loop thread.
- **Expected behavior & Acceptance Criteria:**
  1. New `backend/core/db_async.py` provides `run_db_read(fn, *args, **kwargs)` (non-blocking `asyncio.to_thread`) and `run_db_write(fn, *args, **kwargs)` (serialized through an `asyncio.Lock` + single-writer worker thread, copying `contextvars` so `request_owner` stays intact!).
  2. All synchronous functions in `database.py` and `report_service.py` remain 100% compatible with existing sync unit tests.
  3. `LoadEngine._finish_run()`, `report_router.py`, `profile_router.py`, `load_router.py` (`/traffic/config`), and `journey_router.py` (`/journey`, `/journey/save`) offload SQLite reads/writes asynchronously via `run_db_read` / `run_db_write`.
  4. Async concurrency test verifies event-loop latency remains low (`< 20ms`) even when a slow SQLite write executes alongside concurrent `/api/load/status` / heartbeat tasks, plus concurrent `save_run` calls serialize cleanly without lock errors.

---

## 2. Affected Files
- `[NEW]` `backend/core/db_async.py` — `run_db_read` & serialized `run_db_write` with contextvar propagation and dedicated single-writer `ThreadPoolExecutor(max_workers=1)`.
- `[MODIFY]` `backend/core/load_engine.py` — await `run_db_write(save_run, sqlite_record)` in `_finish_run()`.
- `[MODIFY]` `backend/api/report_router.py`, `backend/api/profile_router.py`, `backend/api/load_router.py`, `backend/api/journey_router.py` — await `run_db_read` / `run_db_write` on SQLite endpoints.
- `[NEW]` `supporting files/testing/unit/test_async_db_offload.py` — test that slow SQLite operations offloaded via `run_db_read` / `run_db_write` do not block concurrent event-loop heartbeats, preserve `request_owner` ContextVar, and serialize concurrent writers cleanly.

---

## 3. Detailed Execution Prompt (Issue 5 — `SCALE-05`)

> **Task:** Implement `backend/core/db_async.py` and offload blocking SQLite reads/writes from `LoadEngine._finish_run()` and async API routers without breaking synchronous test helpers.
>
> **Exact Steps to Execute:**
> 1. Create `backend/core/db_async.py` with `run_db_read(fn, *args, **kwargs)` (`asyncio.to_thread`, contextvar-preserving) and `run_db_write(fn, *args, **kwargs)` running sequentially on a single daemon writer thread executor (`ThreadPoolExecutor(max_workers=1, thread_name_prefix="pusher-db-writer")`) with `contextvars.copy_context().run(...)` so SQLite WAL writes never contend or block the FastAPI loop.
> 2. Update `LoadEngine._finish_run()` (`load_engine.py`), `report_router.py`, `profile_router.py`, `load_router.py` (`/traffic/config`), and `journey_router.py` (`/journey`, `/journey/save`) to `await run_db_read(...)` / `await run_db_write(...)`.
> 3. Add `supporting files/testing/unit/test_async_db_offload.py` testing: (a) asyncio loop ticks keep firing unblocked while a blocking SQLite write runs in `run_db_write`, (b) `request_owner` propagates into both read & write worker threads, (c) concurrent `run_db_write` calls serialize sequentially, and (d) FastAPI `/api/history`, `/api/profile`, and `/api/traffic/config` work cleanly end-to-end.
> 4. Verify with `test_async_db_offload.py` + `test_database_persistence.py` + `test_stage5_reports_history.py` + full `py -m pytest "supporting files/testing/unit" -q --tb=short`, then save `SCALE-05 - Non-Blocking DB IO.md`.
