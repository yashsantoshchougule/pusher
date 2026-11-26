# Gate 3 Execution Prompt — Feature 4: Unified Simple Health Graph (`ProjectHealthChart.jsx` + `timeline_points_json`)

## Objective
Persist compact 1-second timeline points (`timeline_points_json <= 600` points) in `test_runs` and render ONE unified, crisp, beginner-friendly SVG chart component (`frontend/src/components/dashboard/ProjectHealthChart.jsx`) across **Live Dashboard (`1.`)**, **`5. Test History`** (inline expanded drawer), and **`6. Reports`**.

## Deliverables
1. **`backend/core/database.py` & `backend/core/report_service.py`**:
   - Add `timeline_points_json TEXT NOT NULL DEFAULT '[]'` column migration to `test_runs`.
   - Normalize and downsample `timeline_points` to `<= 600` points cleanly (`{"t", "vus", "rps", "p95_ms", "error_pct"}`) on `save_run()`.
   - Return `timeline_points` in `_row_to_dict()` (with fallback derivation from `timeseries` if `timeline_points_json` is empty on older records).
2. **`backend/core/load_engine.py`**:
   - Ensure `_sample_run()` records `timeline_points` format cleanly (`t`, `vus`, `rps`, `p95_ms`, `error_pct`) and emits compact `timeline_points` (or `timeseries` mapped cleanly) in live telemetry / `get_status()` + `sqlite_record`.
3. **Frontend Component `frontend/src/components/dashboard/ProjectHealthChart.jsx`**:
   - Pure responsive SVG (`viewBox="0 0 800 280"`) with:
     - 3 soft health background bands (`Smooth` green `#f0fdf4`, `Slowing` amber `#fffbeb`, `Crashing` red `#fef2f2`)
     - Soft Sage/Green shaded **Active Users (VUs)** area curve
     - Dark Forest-Green (`#14532d`) smooth line for **Response Time (`p95_ms`)**
     - Coral Red (`#dc2626`) line for **Error Rate (`error_pct`)**
     - Vertical **Breaking Point Pin** at `crashSummary.first_error_sec` (`Started failing: X users`)
     - Hover crosshair & interactive tooltip (`Time`, `Active Users`, `Response Speed`, `Error Rate`, `RPS`)
     - 1-line **Plain-English Verdict Bar** below chart (`crashSummary?.plain_english_verdict`).
4. **Mount Identically Across 3 Views**:
   - `1. Dashboard` (`OverviewBoxes.jsx`): Live updates every second from `telemetry.points` / `runStatus.timeline_points`.
   - `5. Test History` (`TestHistoryView.jsx`): Expanded run drawer renders `<ProjectHealthChart />`.
   - `6. Reports` (`ReportsView.jsx`): Single run report renders `<ProjectHealthChart />` above detailed breakdowns.
