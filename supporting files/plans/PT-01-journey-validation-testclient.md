# PT-01 — `test_journey_validation.py` fails with `TestClient` `client` keyword error

Priority: Must Fix · Source: `py -m pytest "supporting files/testing/unit"` (4 parameterized failures in `test_invalid_steps_rejected_at_each_entry_point`)

## Problem & Root Cause

`supporting files/testing/unit/test_journey_validation.py:24` constructs `TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000))`. On Starlette `0.38.6` (active in Python 3.13), `TestClient.__init__` does not accept a `client` keyword argument, raising `TypeError: TestClient.__init__() got an unexpected keyword argument 'client'` for all 4 parameterized cases (`headers` list, unsafe `headers`, invalid `method`, non-int `expected_status`).

The `client=("127.0.0.1", 50000)` address is required so `offline_connection()` in `backend/api/auth_deps.py` sees a loopback client IP instead of Starlette's default `"testclient"` placeholder.

## Implementation Prompt

1. Inspect `supporting files/testing/unit/test_journey_validation.py`.
2. Add a local `_test_client(target_app, *, base_url, client)` helper that passes `client=client` directly when `TestClient.__init__` supports it, and otherwise wraps the ASGI `scope["client"]` for HTTP/WebSocket scopes so both Starlette `0.38.6` and newer Starlette versions behave identically.
3. Replace the direct `TestClient(..., client=...)` call on line 24 with `_test_client(...)`, keeping all assertions, temporary SQLite isolation, and offline-mode checks intact.
4. Run `py -m pytest "supporting files/testing/unit/test_journey_validation.py" -v` and confirm all 6 tests pass.

## Verification

- **Result**: `Resolved`
- **How it occurred**: `TestClient(app, base_url=..., client=("127.0.0.1", 50000))` raised `TypeError` on Starlette `0.38.6` (Python 3.13) because `TestClient.__init__` only accepts `client` in newer Starlette versions.
- **How it was solved**: Added `_test_client()` in `supporting files/testing/unit/test_journey_validation.py` to pass `client=client` when supported and otherwise wrap ASGI `scope["client"]` for HTTP/WebSocket scopes.
- **Testing**: `py -m pytest "supporting files/testing/unit/test_journey_validation.py" -v` -> **6 passed in 3.05s** (all 4 invalid-step rejection cases + both worker-error/zero-request report cases).
