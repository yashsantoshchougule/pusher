# ISSUE-08 Execution Prompt — Theme Token Cleanup & Final End-to-End Verification

- **Issue ID:** `ISSUE-08`
- **Priority:** Should Fix
- **Master Report:** [master_issue_report.md](./master_issue_report.md)

## Problem
1. `frontend/tailwind.config.js` defines unused theme color tokens not referenced anywhere in `frontend/src/`.
2. Local dev mode / offline banner on `LoginPage.jsx` and live dev server ports (`127.0.0.1:8000` backend and `127.0.0.1:3000` frontend) need clean verification alongside full backend + frontend regression test suites.

## Implementation Steps
1. Clean unused palette tokens from `frontend/tailwind.config.js` while keeping core config intact (`Olive/Cream` login and `Light/Dark` dashboard themes remain preserved).
2. Ensure offline-dev banner wording on `LoginPage.jsx` (if shown) clearly explains local operator access without noisy warnings.
3. Verify `npm --prefix frontend run build` builds cleanly with zero chunk warnings.
4. Start/verify backend (`127.0.0.1:8000`) and frontend (`127.0.0.1:3000`, stopping stale `:3001` process if left over from earlier testing).
5. Run all backend pytest suites (`py -m pytest "supporting files/testing/unit" -q` and `.venv\Scripts\python.exe -m pytest "supporting files/testing/unit/test_remediation_fixes.py" -q`) and all Node unit/view tests (`test_*.mjs`, `test_*.cjs`, `react_view_fixture.mjs`) and record all exact outputs in `issue-08-verified-report.md`.
