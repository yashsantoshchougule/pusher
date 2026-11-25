# PT-02 — `test_operator_access.py` fails with `TestClient` `client` keyword error

Priority: Must Fix · Source: `py -m pytest "supporting files/testing/unit"` (`test_offline_is_explicit_and_loopback_only`)

## Problem & Root Cause

`supporting files/testing/unit/test_operator_access.py:124` and `:127` construct `TestClient(app, base_url="http://localhost:8000", client=("127.0.0.1", 50000))` and `client=("192.0.2.1", 50000)` to verify that `offline_connection()` allows loopback clients and rejects remote clients. On Starlette `0.38.6` (Python 3.13), `TestClient.__init__` does not accept `client=...`, raising `TypeError: TestClient.__init__() got an unexpected keyword argument 'client'`.

## Implementation Prompt

1. Inspect `supporting files/testing/unit/test_operator_access.py`.
2. Add a local `_test_client(target_app, *, base_url, client)` helper that passes `client=client` when `TestClient.__init__` supports it, and otherwise wraps ASGI `scope["client"]` for HTTP/WebSocket scopes.
3. Update `test_offline_is_explicit_and_loopback_only` to use `_test_client(...)` for both the loopback (`127.0.0.1`) and remote (`192.0.2.1`) clients, preserving all status/origin/loopback assertions.
4. Run `py -m pytest "supporting files/testing/unit/test_operator_access.py" -v` and confirm all tests pass.

## Verification

- **Result**: `Resolved`
- **How it occurred**: `TestClient(app, base_url="http://localhost:8000", client=...)` raised `TypeError` on Starlette `0.38.6` (Python 3.13) because `TestClient.__init__` only accepts `client` in newer Starlette versions.
- **How it was solved**: Added `_test_client()` in `supporting files/testing/unit/test_operator_access.py` to pass `client=client` when supported and otherwise wrap ASGI `scope["client"]` for HTTP/WebSocket scopes, testing both `127.0.0.1` (loopback allowed) and `192.0.2.1` (remote rejected).
- **Testing**: `py -m pytest "supporting files/testing/unit/test_operator_access.py" -v` -> **5 passed in 0.79s**.
