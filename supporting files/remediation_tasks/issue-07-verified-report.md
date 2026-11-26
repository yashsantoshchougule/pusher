# ISSUE-07 Verified Report — Frontend Bundle Code-Splitting (`< 500 kB`) & `51 MB` RAM Parity

- **Issue ID:** `ISSUE-07`
- **Priority:** Should Fix
- **Prompt Executed:** [issue-07-bundle-split-ram-parity-prompt.md](./issue-07-bundle-split-ram-parity-prompt.md)
- **Status:** `Verified & Done`

## Root Cause
1. Static top-level imports in `App.jsx` and `DashboardPage.jsx` bundled all routes and all 7 dashboard views into a single `611.36 kB` chunk, exceeding Vite's `500 kB` threshold.
2. Profile RAM defaults enforced a `50 MB` floor (`profile_router.py`, `profile_service.py`, `ProfileView.jsx`), disagreeing with `load_router.py`'s `51 MB` minimum.

## Changes Applied
- [profile_router.py](file:///c:/yash/projects/pusher/backend/api/profile_router.py) & [profile_service.py](file:///c:/yash/projects/pusher/backend/core/profile_service.py): Aligned `default_ram_ceiling_mb` minimum floor to `51` (`ge=51`, `max(51, ...)`).
- [ProfileView.jsx](file:///c:/yash/projects/pusher/frontend/src/components/dashboard/ProfileView.jsx): Aligned RAM slider `min="51"` and label `51 MB (Micro)`.
- [App.jsx](file:///c:/yash/projects/pusher/frontend/src/App.jsx): Code-split `DashboardPage`, `WafSetupPage`, `AccountRecoveryPage`, and `TermsPage` via `React.lazy(...)` with `<Suspense>` fallbacks (keeping sub-view imports synchronous inside `DashboardPage` for full React SSR/fixture compatibility while staying well under `500 kB`).
- [test_remediation_fixes.py](file:///c:/yash/projects/pusher/supporting%20files/testing/unit/test_remediation_fixes.py): Added `test_profile_ram_floor_matches_51mb_load_minimum`.

## Verification Results
- Ran `npm --prefix frontend run build`:
  - Built in `4.95s` with **zero** `> 500 kB` chunk warnings (`dist/assets/index-BnzcDXoY.js` = `398.84 kB`, `DashboardPage-Bzyb5lfu.js` = `198.69 kB`, `WafSetupPage` = `9.74 kB`).
- Ran `.venv\Scripts\python.exe -m pytest "supporting files/testing/unit/test_remediation_fixes.py" -q`:
  - **`8 passed`**
- Ran `node --test "supporting files/testing/unit/react_view_fixture.mjs"`:
  - **`1 passed`**
