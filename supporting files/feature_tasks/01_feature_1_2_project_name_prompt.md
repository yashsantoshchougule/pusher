# Gate 1 Execution Prompt — Features 1 & 2: Auto-Detect Project Name + Pre-Test Name Input

## Objective
Enable automatic, low-RAM (<= 8 KB streamed) project name detection when a target URL is checked/entered, persist `project_name` per operator (`user_id`) in `active_target_state` and `test_runs`, and provide editable `PROJECT NAME` controls on `2. Verify Target`, `1. Dashboard`, and `3. Traffic Setup` before starting any load test.

## Exact Targets & Changes

### 1. Backend (`backend/core/target_service.py`)
- Add `detect_hostname_fallback(target_url: str) -> str`:
  - Strip leading `www.` and `api.`, strip common suffixes (`.vercel.app`, `.onrender.com`, `.netlify.app`, `.com`, `.dev`, `.io`), split tokens on `-`/`.`, Title-Case, cap at 50 chars (e.g. `https://api.veribite.vercel.app` -> `"Veribite"`). Return `"Unnamed Project"` if hostname empty.
- Add `extract_project_name_from_html(html_text: str, target_url: str) -> tuple[str, str]`:
  1. `<meta property="og:site_name" content="...">` or `<meta name="application-name" content="...">` -> source `"meta"`
  2. `<title>...</title>` (trim suffix after `|`, `—`, `–`, ` - ` when raw length > 32, decode HTML entities, cap at 50 chars) -> source `"title"`
  3. `detect_hostname_fallback(target_url)` -> source `"hostname"`
- Add `async def detect_project_name(target_url: str, is_sandbox: bool = False) -> dict`:
  - If `is_sandbox`: return `{"project_name": "Pusher Sandbox", "source": "sandbox"}`.
  - Parse URL cleanly via `parse_target(target_url)`.
  - Stream GET via `target_client(url, False, timeout=httpx.Timeout(3.0), follow_redirects=True)`, reading **at most 8,192 bytes (`8 KB`)** across bounded chunks, closing stream immediately.
  - On non-HTML content-type, network failure, or parse miss, fall back cleanly to `detect_hostname_fallback(target_url)` (`source: "hostname"`).
- Add `project_name: str = ""` field to `ActiveTargetStore` (`_load_from_db`, `_save_to_db`, `set_target`, `set_project_name`).

### 2. SQLite Schema & Persistence (`backend/core/database.py`, `backend/core/report_service.py`)
- Add non-destructive column migration `project_name TEXT NOT NULL DEFAULT ''` to `active_target_state` and `test_runs`.
- Add `db_update_active_project_name(project_name: str, user_id: str) -> str` helper.
- Include `project_name` in `db_get_active_target`, `db_save_active_target`, `save_run`, `_SUMMARY_FIELDS`, `_row_to_dict`, and history search (`q` searches `project_name`, `run_id`, and `target_url`).

### 3. API Routes & Engine (`backend/api/target_router.py`, `backend/api/load_router.py`, `backend/core/load_engine.py`)
- Keep `validate_target_url()` pure (DNS/sandbox only so `test_dns_readiness_does_not_request_ownership_challenge` remains intact).
- In `POST /api/target/validate-url`: when `result.get("ready")`, call `detect_project_name()` and return `detected_project_name` and `detected_project_source`.
- Expose `POST /api/target/detect-name` (`ValidateSsrfRequest`) returning `detect_project_name()`.
- Expose `PUT /api/target/project-name` (`ProjectNameRequest`) saving operator `project_name` to `active_target_state`.
- Include `project_name` in `GET /api/target/status`.
- Accept optional `project_name` in `LoadStartRequest` (`POST /api/load/start`) and `LoadEngine.start(...)`; resolve fallback cleanly (`explicit -> active_target.project_name -> sandbox/hostname`), expose in `get_status()`, WebSocket ticks, and `sqlite_record`.

### 4. Frontend Pre-Test Inputs (`DashboardPage.jsx`, `VerifyTargetView.jsx`, `OverviewBoxes.jsx`, `TrafficSetupView.jsx`)
- Hydrate `projectName` & `projectNameSource` in `DashboardPage.jsx` from `/api/target/status` and `/api/target/validate-url` (do not clobber user manual edits once dirty for that target).
- Persist edited name via `PUT /api/target/project-name` (`handleSaveProjectName`) and send `project_name` inside `POST /api/load/start`.
- Add `PROJECT NAME` editable input with `Auto-detected` / `Custom` badge on:
  - `VerifyTargetView.jsx` (`2. Verify Target`)
  - `OverviewBoxes.jsx` (`1. Dashboard` right next to `START LOAD TEST NOW`)
  - `TrafficSetupView.jsx` (`3. Traffic Setup` right next to `SAVE & LAUNCH LOAD TEST`)

## Gate 1 Verification Criteria
- Unit tests confirm `<meta og:site_name>`, `<title>` truncation, HTML-less JSON hostname fallback (`Veribite`), `is_sandbox` -> `"Pusher Sandbox"`, and strict `<= 8,192` bytes streamed read cap.
- `test_dns_readiness_does_not_request_ownership_challenge` still passes untouched.
- API & DB tests verify `PUT /api/target/project-name`, `POST /api/load/start` storing `project_name` per `user_id`.
- `npm --prefix frontend run build` succeeds with 0 errors.
