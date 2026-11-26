# ISSUE-04 Execution Prompt — Fix `X-Pusher-Device-ID` CORS Header & Port Origins

- **Issue ID:** `ISSUE-04`
- **Priority:** Must Fix
- **Master Report:** [master_issue_report.md](./master_issue_report.md)

## Problem
1. Frontend `telemetry.js` sends `X-Pusher-Device-ID` on requests and WebSocket session control, while `backend/main.py` `CORSMiddleware` only lists `allow_headers=["Authorization", "Content-Type", "apikey", "X-Requested-With"]`, causing CORS preflight (`OPTIONS`) failures when custom device-ID headers are transmitted cross-origin.
2. `backend/core/config.py` `allowed_origins` only includes `:3000` and `:5173`, missing `:3001` fallback origins when Vite binds to `3001`.

## Implementation Steps
1. Add `"X-Pusher-Device-ID"` to `CORSMiddleware(allow_headers=...)` in `backend/main.py`.
2. Add `"http://localhost:3001"` and `"http://127.0.0.1:3001"` to `Settings.allowed_origins` in `backend/core/config.py`.
3. Add CORS preflight tests (`OPTIONS` on `/api/load/status` from `http://localhost:3000` and `http://localhost:3001` with `X-Pusher-Device-ID`) in `supporting files/testing/unit/test_remediation_fixes.py` and verify via `py -m pytest`.
