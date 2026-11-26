# Gate 1 Verified Report — Features 1 & 2 (Project Name Auto-Detect & Pre-Test Inputs)

**Status:** VERIFIED & COMPLETE

## What Was Built
1. **8 KB Safe Auto-Detector ([target_service.py](file:///c:/yash/projects/pusher/backend/core/target_service.py)):**
   - Added `detect_hostname_fallback()`, `extract_project_name_from_html()`, and `detect_project_name(target_url, is_sandbox)`.
   - Priority: `is_sandbox` -> `"Pusher Sandbox"` -> `<meta og:site_name>` / `<meta application-name>` -> `<title>` (suffix-trimmed when `> 32` chars, capped at 50) -> Title-Cased hostname fallback (e.g. `https://api.veribite.vercel.app` -> `"Veribite"`).
   - Streams up to **8,192 bytes** with SSRF-checked `target_client` across safe redirects and closes immediately.
2. **Database & API Persistence ([database.py](file:///c:/yash/projects/pusher/backend/core/database.py), [target_router.py](file:///c:/yash/projects/pusher/backend/api/target_router.py), [report_service.py](file:///c:/yash/projects/pusher/backend/core/report_service.py), [load_router.py](file:///c:/yash/projects/pusher/backend/api/load_router.py), [load_engine.py](file:///c:/yash/projects/pusher/backend/core/load_engine.py)):**
   - Migrated `project_name` column onto `active_target_state` and `test_runs` (scoped by `user_id`, searchable via `q`).
   - Added `POST /api/target/detect-name`, `PUT /api/target/project-name`, `detected_project_name` on `POST /api/target/validate-url`, `project_name` on `GET /api/target/status` & `POST /api/load/start`.
3. **Frontend Pre-Test UI ([DashboardPage.jsx](file:///c:/yash/projects/pusher/frontend/src/pages/DashboardPage.jsx), [VerifyTargetView.jsx](file:///c:/yash/projects/pusher/frontend/src/components/dashboard/VerifyTargetView.jsx), [OverviewBoxes.jsx](file:///c:/yash/projects/pusher/frontend/src/components/dashboard/OverviewBoxes.jsx), [TrafficSetupView.jsx](file:///c:/yash/projects/pusher/frontend/src/components/dashboard/TrafficSetupView.jsx)):**
   - Editable `PROJECT NAME` input with `Auto-detected` / `Custom` badge on `2. Verify Target`, `1. Dashboard` (next to `START LOAD TEST NOW`), and `3. Traffic Setup`.

## Verification Evidence
- `py -m pytest "supporting files/testing/unit/test_project_reports_pdf.py" "supporting files/testing/unit/test_outbound_target_policy.py" -q` -> **13 passed**.
- `npm --prefix frontend run build` -> **built cleanly (`0` errors)**.
