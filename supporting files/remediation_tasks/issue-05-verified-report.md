# ISSUE-05 Verified Report — Implement Client Disconnect Guard (15s Auto-Abort)

- **Issue ID:** `ISSUE-05`
- **Priority:** Should Fix
- **Prompt Executed:** [issue-05-client-disconnect-guard-prompt.md](./issue-05-client-disconnect-guard-prompt.md)
- **Status:** `Verified & Done`

## Root Cause
Previously, WebSocket disconnection in `backend/api/load_router.py` only removed the socket from `ConnectionManager` without starting a disconnect grace timer, leaving orphaned load tests running even after all operator browser tabs disconnected.

## Changes Applied
- [load_engine.py](file:///c:/yash/projects/pusher/backend/core/load_engine.py):
  - Added `DISCONNECT_GRACE_SECONDS = 15.0` and `_ACTIVE_WS_WATCHERS`, plus `register_ws_watcher()` / `unregister_ws_watcher()` helpers.
  - Added `LoadEngine.touch_client_keepalive()`, `on_ws_watcher_connected()`, `on_ws_watcher_disconnected()`, `_disconnect_grace_watchdog()`, and `_cancel_disconnect_guard()`, integrated with `start()`, `get_status(owner_id)`, and `_finish_run()`.
  - Once an operator attaches a WebSocket watcher to a running test, dropping the last WebSocket waits `DISCONNECT_GRACE_SECONDS` (15s) and aborts (`STOPPED (CLIENT_DISCONNECTED)`) unless another WS connects or `/api/load/status` polls within the grace period. Headless API runs without WS watchers stay unaffected.
- [load_router.py](file:///c:/yash/projects/pusher/backend/api/load_router.py):
  - Hooked `register_ws_watcher` and `unregister_ws_watcher` into `websocket_telemetry` connect/disconnect lifecycle.
- [test_remediation_fixes.py](file:///c:/yash/projects/pusher/supporting%20files/testing/unit/test_remediation_fixes.py):
  - Added `test_client_disconnect_guard_aborts_when_ws_drops_and_preserves_headless_and_polled_runs`.

## Verification Results
- Ran `.venv\Scripts\python.exe -m pytest "supporting files/testing/unit/test_remediation_fixes.py" "supporting files/testing/unit/test_concurrent_runs.py" -q`:
  - **`6 passed`** (verified WS disconnect triggers `CLIENT_DISCONNECTED` abort after grace period, HTTP status polling and WS reconnect keep runs alive, and headless runs complete normally).
