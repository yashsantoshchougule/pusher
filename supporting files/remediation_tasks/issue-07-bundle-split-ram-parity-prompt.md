# ISSUE-07 Execution Prompt — Frontend Bundle Code-Splitting (`< 500 kB`) & `51 MB` RAM Parity

- **Issue ID:** `ISSUE-07`
- **Priority:** Should Fix
- **Master Report:** [master_issue_report.md](./master_issue_report.md)

## Problem
1. Production Vite build (`npm --prefix frontend run build`) emits a single `~611 kB` JS bundle triggering Vite's `> 500 kB` chunk-size warning because `App.jsx` and `DashboardPage.jsx` statically import all route pages and all 7 dashboard sub-views eagerly.
2. `backend/api/profile_router.py` (`ge=50`) and `backend/core/profile_service.py` (`max(50, ...)`) allow a `50 MB` RAM ceiling default while `load_router.py` and `TrafficSetupView.jsx` enforce `51 MB` (`ge=51`), causing validation mismatch if a user sets `50 MB` in Profile and tries to run a test.

## Implementation Steps
1. Update `profile_router.py` (`ge=51`), `profile_service.py` (`max(51, ...)`), and `ProfileView.jsx` slider/range minimum (`51` instead of `50` / consistent label) so Profile defaults align cleanly with `51 MB` everywhere.
2. Convert heavy routes (`DashboardPage`, `WafSetupPage`, `AccountRecoveryPage`, `TermsPage`) in `frontend/src/App.jsx` and sub-views (`VerifyTargetView`, `TrafficSetupView`, `ApiBuilderView`, `TestHistoryView`, `ReportsView`, `ProfileView`) in `frontend/src/pages/DashboardPage.jsx` to `React.lazy(...)` wrapped with clean `<Suspense fallback={...}>` boundaries.
3. Add a backend unit test verifying `PUT /api/profile` rejects `50` (`422`) and clamps/accepts `51` (`200`) in `test_remediation_fixes.py`.
4. Run `npm --prefix frontend run build` and confirm zero chunks exceed `500 kB` (no Vite chunk warning), and run `py -m pytest` + `node --test "supporting files/testing/unit/react_view_fixture.mjs"`.
