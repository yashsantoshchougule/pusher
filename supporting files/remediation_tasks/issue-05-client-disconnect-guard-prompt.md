# ISSUE-05 Execution Prompt — Implement Client Disconnect Guard (15s Auto-Abort)

- **Issue ID:** `ISSUE-05`
- **Priority:** Should Fix
- **Master Report:** [master_issue_report.md](./master_issue_report.md)

## Problem
`safety_limits.md` requires a Client Disconnect Guard: if an operator's browser/client disconnects mid-test and does not reconnect within 15 seconds, the engine must safely abort the active run so orphaned load cannot continue hitting targets. Currently, WS disconnect in `load_router.py` only removes the socket without notifying `LoadEngine` or scheduling an abort watchdog.

## Implementation Steps
1. Add `DISCONNECT_GRACE_SECONDS = 15.0` and lightweight per-owner active WS watcher tracking in `backend/core/load_engine.py`.
2. Track client signals cleanly per `(owner_id, run_id)`:
   - Connecting a WebSocket marks `_saw_ws_watcher = True` (including if WS was already open before `start()`), cancels any pending disconnect watchdog, and refreshes client keepalive.
   - Disconnecting the last WS for `owner_id` starts `_disconnect_grace_watchdog()` when `_saw_ws_watcher` is `True`.
   - HTTP keepalive polls (`get_status(owner_id)` from `/api/load/status`) refresh `_last_client_keepalive_ts` so HTTP-polling fallbacks stay alive while disconnected WS can recover.
   - If `DISCONNECT_GRACE_SECONDS` elapses without WS reconnect or status poll keepalive, call `request_stop("STOPPED (CLIENT_DISCONNECTED)")`.
   - Headless API runs with zero WS watchers attached stay completely unaffected.
   - Cancel any pending disconnect watchdog in `_finish_run()`.
3. Hook WS connect/disconnect lifecycle into `backend/api/load_router.py` (`websocket_telemetry`).
4. Add unit + FastAPI WebSocket integration tests (using a fast monkeypatched grace window e.g. `0.25s`) verifying:
   - closing the last WS aborts the active run with `CLIENT_DISCONNECTED`,
   - `/api/load/status` polling or WS reconnect prevents abort,
   - headless runs without WS watchers complete normally.
