# ISSUE-03 Verified Report — Sync `.venv` Python Packages & Verify Parity

- **Issue ID:** `ISSUE-03`
- **Priority:** Must Fix
- **Prompt Executed:** [issue-03-venv-sync-prompt.md](./issue-03-venv-sync-prompt.md)
- **Status:** `Verified & Done`

## Root Cause
The local `.venv\Scripts\python.exe` environment was missing `aiohttp`, `winloop`, `reportlab`, `pytest`, and `pytest-asyncio`, causing `AiohttpLoadClient`, PDF report generation, and test runs inside `.venv` to fail or fall back differently from the system `py` interpreter.

## Resolution Applied
- Synced `backend/requirements.txt` plus `pytest` and `pytest-asyncio` into `.venv\Scripts\python.exe` (Python 3.12.13) via `uv pip install`.

## Verification Results
- Ran `.venv\Scripts\python.exe -c "import aiohttp, reportlab, psutil, fastapi, pytest; from backend.core.http_runner import get_fast_loop_factory; ..."`:
  - `core_ok 3.14.5 4.5.1 9.2.0`
  - `get_fast_loop_factory()` resolved to `<function new_event_loop>` from module `winloop`.
- Ran `.venv\Scripts\python.exe -m pytest "supporting files/testing/unit/test_remediation_fixes.py" -q`:
  - **`3 passed in 5.18s`**
