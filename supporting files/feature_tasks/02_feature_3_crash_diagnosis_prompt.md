# Gate 2 Execution Prompt — Feature 3: Crash & Failure Point Breakdown

## Objective
Track per-endpoint and per-step request reliability, exact first error timing/concurrency, HTTP/network failure classification, and overall crash diagnosis (`failure_breakdown` + `crash_summary`) in both single-process and multi-process worker pools, stream them over WebSocket, persist them in SQLite `test_runs`, and display `<FailureDiagnosisCard />` on Live Dashboard, Test History, and Reports.

## Deliverables
1. **`backend/core/crash_diagnosis.py`**:
   - Shared helper with `classify_error_code(status_code, timed_out)`, `plain_reason_for(error_code, error_rate_pct, p95_ms)`, and `compute_crash_diagnosis(...)` returning `(failure_breakdown: list[dict], crash_summary: dict)`.
2. **`backend/core/worker_process.py` & `backend/core/load_engine.py`**:
   - Track lightweight per-part metrics (`"Step X: METHOD /path"` or `"METHOD /path"`): requests, failed count, status code map (`"500"`, `"502"`, `"503"`, `"504"`, `"429"`, `"TIMEOUT"`, `"CONNECTION_REFUSED"`), compact latency histogram for `p95_latency_ms`, and earliest `(first_error_at_sec, first_error_at_vus)`.
   - Transport compact `part_deltas` across multiprocessing queues into `_apply_worker_delta()`.
   - Emit `failure_breakdown` and `crash_summary` inside `get_status()`, `broadcast_telemetry()`, and `save_run()`.
3. **`backend/core/database.py` & `backend/core/report_service.py`**:
   - Add `failure_breakdown_json` and `crash_summary_json` columns cleanly to `test_runs`.
4. **Frontend UI (`FailureDiagnosisCard.jsx`, `OverviewBoxes.jsx`, `TestHistoryView.jsx`, `ReportsView.jsx`, `DashboardPage.jsx`)**:
   - Create `FailureDiagnosisCard.jsx` displaying top verdict pill (`SMOOTH` / `SLOWED DOWN` / `CRASHED / FAILING`), `plain_english_verdict`, safe VU capacity, breaking point VU/sec, and ranked endpoint table with traffic-light health badges.
