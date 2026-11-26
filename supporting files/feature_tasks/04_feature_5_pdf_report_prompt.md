# Gate 4 Execution Prompt — Feature 5: Vector PDF Report Export (`reportlab`)

## Objective
Add pure-Python vector PDF report generation using `reportlab`, expose `GET /api/reports/{run_id}/pdf` scoped to the authenticated operator (`user_id`), and wire `[ DOWNLOAD PDF REPORT ]` in both `5. Test History` and `6. Reports`.

## Deliverables
1. **Dependencies (`backend/requirements.txt`, `pyproject.toml`, `pip install reportlab`)**:
   - Add `reportlab` to both `backend/requirements.txt` and `pyproject.toml` and install it cleanly.
2. **Vector PDF Builder (`backend/core/pdf_report_service.py`)**:
   - Render an A4 light-themed report via `io.BytesIO()` + ReportLab (`SimpleDocTemplate`, `Table`, `Drawing`):
     - Section 1 — Header: Project Name (prominent title), Target URL, Run ID, Timestamp, Traffic Mode, Verdict Status Pill (`SMOOTH` / `SLOWED DOWN` / `CRASHED / FAILING`)
     - Section 2 — 4-box KPI strip: Safe User Capacity, Peak Users Tested, Avg / P95 Latency, Error Rate (%)
     - Section 3 — Identical Vector Project Health Graph (`Drawing` with green/amber/red zone bands, sage Active Users polygon, forest-green Response Time curve, coral-red Error % curve, breaking-point vertical dashed marker + label, clear legend, and 1-line verdict summary underneath)
     - Section 4 — Crash & Failure Point Table (Project Part / Step, Requests, Failed, Error %, First Error @ VUs/sec, Error Codes, Health, Plain-English Reason)
     - Section 5 — Footer with page number, Guard verification badge, and RAM / 4 KB Chunk-Discard info.
3. **API Endpoint (`backend/api/report_router.py`)**:
   - `GET /api/reports/{run_id}/pdf`: lookup `get_run(run_id)` scoped to `request_owner` (return `404` if missing or owned by another user), return `StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": ...})`.
4. **Frontend UI (`DashboardPage.jsx`, `ReportsView.jsx`, `TestHistoryView.jsx`)**:
   - Add `handleDownloadPdf(runId, projectName)` calling `operatorFetch('/api/reports/' + encodeURIComponent(runId) + '/pdf')` -> blob download.
   - Wire `[ DOWNLOAD PDF REPORT ]` buttons cleanly on `6. Reports` and `5. Test History`.
