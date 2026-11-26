# `SCALE-04` Plan & Detailed Execution Prompt

- **Issue ID:** `SCALE-04` (Position 4 of 6 in [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md))
- **Exact Title:** Support Multiple Concurrent Runs (RunManager instead of Global LoadEngine Singleton)
- **Priority:** `Must Fix`

---

## 1. Problem, Baseline & Confirmed Cause
- **Current bottleneck:** `load_engine` is instantiated as a single process-wide global (`backend/core/load_engine.py:1378`), and `load_router.py` rejects `POST /api/load/start` with `409 Conflict` whenever *any* operator has an active test.
- **Visible impact:** Only one operator on the entire Pusher backend can run a load test at a time, and concurrent run telemetry/lifecycle cannot be addressed independently by `run_id`.
- **Expected behavior & Acceptance Criteria:**
  1. New `backend/core/run_manager.py` introduces `RunManager` managing multiple concurrent `LoadEngine` instances keyed by `run_id` and `owner_id`, sharing `ConnectionManager` (which already scopes WS broadcasts per `owner_id`).
  2. Different authenticated operators (`alice` and `bob`) can start, monitor via `/api/load/status` (and optional `?run_id=`) / WebSocket `/api/load/ws`, `simulate-spike`, and independently `stop` concurrent runs at the same time.
  3. Same operator cannot start overlapping runs simultaneously unless stopped (`409`), and total active VUs across all concurrent runs enforce the global host FD worker ceiling (`get_os_fd_cap()`).
  4. Guard revocation (`target_router.py`, `target_service.py`) and server shutdown (`main.py`) stop all matching/active concurrent engines cleanly.
  5. Backward compatibility preserved 100% for all existing single-engine unit tests (`test_operator_access.py`, `test_dry_run_controls.py`, `test_guard_deadline.py`, `test_journey_secret_storage.py`, `test_target_privacy.py`) including `monkeypatch.setattr(load_router, "load_engine", ...)` and `monkeypatch.setattr(load_engine, ...)`.

---

## 2. Affected Files
- `[NEW]` `backend/core/run_manager.py` — `RunManager` registry with per-owner isolation, shared host FD VU quota accounting, `run_id` lookup, guard revocation stop hook, and `stop_all()`.
- `[MODIFY]` `backend/api/load_router.py` — route `/load/start`, `/load/stop`, `/load/status`, `/load/simulate-spike`, and `/load/ws` through `run_manager` (honoring `load_engine` monkeypatches seamlessly), adding optional `run_id: str | None = None` query support on status/simulate-spike and listing active run capacity.
- `[MODIFY]` `backend/api/target_router.py`, `backend/core/target_service.py`, `backend/main.py` — stop owner-scoped concurrent runs on guard revoke/burn and stop all active runs on FastAPI lifespan shutdown.
- `[NEW]` `supporting files/testing/unit/test_concurrent_runs.py` — tests starting 2 concurrent runs from different JWT users (`alice` & `bob`), verifying telemetry/WebSocket isolation, cross-user `403` isolation, independent `/stop`, and global host FD quota enforcement.

---

## 3. Detailed Execution Prompt (Issue 4 — `SCALE-04`)

> **Task:** Implement `RunManager` (`SCALE-04`) so multiple operators can execute concurrent isolated load tests cleanly while keeping all existing tests green.
>
> **Exact Steps to Execute:**
> 1. **Create `backend/core/run_manager.py`:**
>    - Define `RunManager(default_engine: LoadEngine)`:
>      - Tracks `_runs: dict[str, LoadEngine]` and `_owner_latest: dict[str, LoadEngine]` protected via cleanup of stale finished mappings.
>      - `total_reserved_vus(exclude_owner: str | None = None) -> int`: sums `_worker_limit` (or `target_vus`) across currently running engines so total concurrent VUs across all users never exceed `max_worker_vus`.
>      - `active_engine_for_owner(owner_id, fallback_engine)`: returns the active or most-recent engine belonging to `owner_id` (checking `fallback_engine` first if it was monkeypatched or is owned by `owner_id`).
>      - `acquire_engine_for_start(owner_id, primary_engine)`: raises conflict if `owner_id` already has a running engine; returns `primary_engine` if idle (maintaining test fixtures that inspect `load_engine`), otherwise constructs a new `LoadEngine()` sharing `primary_engine.connection_manager`.
>      - `register_run(engine)` / `find_for_stop(owner_id, run_id, primary_engine)` / `stop_guard_runs(owner_id, guard_id)` / `stop_all(reason)`.
> 2. **Wire `run_manager` into `load_router.py`, `target_router.py`, `target_service.py`, and `main.py`:**
>    - Respect monkeypatched `load_engine` cleanly (if `fallback_engine is not default_engine`, treat it cleanly alongside `run_manager`).
>    - Support optional `run_id: str | None = None` on `GET /api/load/status` and `POST /api/load/simulate-spike`.
>    - Enforce global concurrency headroom (`remaining_worker_vus = max(0, max_worker_vus - active_host_vus)`) when admitting a new run in `/api/load/start`.
>    - Preserve exact `403` (`owner` mismatch) and `409` (`run_id` stale/mismatch) status codes asserted by `test_operator_access.py`.
> 3. **Write & Verify (`SCALE-04` Gate):**
>    - Add `supporting files/testing/unit/test_concurrent_runs.py` verifying simultaneous runs for `alice` and `bob`, independent status & WebSocket streams, `alice` stopping without touching `bob`, and shared FD budget enforcement.
>    - Run `py -m pytest "supporting files/testing/unit/test_concurrent_runs.py" "supporting files/testing/unit/test_operator_access.py" -v`, full `py -m pytest "supporting files/testing/unit" -q --tb=short`, and `check_flask_guard.py`, then record `SCALE-04 - Concurrent RunManager.md`.
