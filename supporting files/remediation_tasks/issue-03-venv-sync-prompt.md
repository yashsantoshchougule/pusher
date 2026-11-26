# ISSUE-03 Execution Prompt — Sync `.venv` Python Packages & Verify Parity

- **Issue ID:** `ISSUE-03`
- **Priority:** Must Fix
- **Master Report:** [master_issue_report.md](./master_issue_report.md)

## Problem
`.venv\Scripts\python.exe` exists in the repository root but is missing `aiohttp`, `winloop`, `reportlab`, `pytest`, and `pytest-asyncio`. Running tests or the server inside `.venv` breaks high-speed load runs and PDF exports.

## Implementation Steps
1. Install runtime requirements (`backend/requirements.txt`) plus dev test packages (`pytest`, `pytest-asyncio`) cleanly into `.venv\Scripts\python.exe` (`uv sync` / `pip`).
2. Confirm `import aiohttp, winloop, reportlab, psutil, fastapi, pytest` succeeds in `.venv` and `.venv\Scripts\python.exe -m pytest "supporting files/testing/unit/test_remediation_fixes.py" -q` passes 100%.
