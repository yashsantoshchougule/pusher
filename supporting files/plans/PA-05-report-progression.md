# PA-05 — Show recorded progression in report details

Priority: Should Fix

Master: https://docs.google.com/document/d/1J9sPxjf_nf7PTuI4aV27e3jL_5rZ59tQ5bM4b3ZOEAs/edit?usp=drivesdk

## Task prompt

Display the recorded run timeline in the single-run report. Read the full detail response's timeseries and show elapsed time, VUs, requests per second, p95, and error rate in chronological order. Preserve real zeros, show unavailable for missing measurements, and explain when older reports have no timeline. Keep export and comparison behavior intact.

## Verified baseline and scope

load_engine.py persists the recorded samples and report_service.py includes them in full detail and export. ReportsView.jsx currently renders report.steps for a legacy summary and never consumes timeseries. The current recorder supports up to 3,600 points, so display 50 rows at a time with navigation to the complete archive. Invalid or absent elapsed times cannot be positioned and are excluded. All recorded fields are displayed as sampled.

## Implementation and verification

1. Add a ReportsView render fixture with unsorted samples, zeros, missing values, and no legacy archive. Establish the missing timeline failure before editing.
2. Add the table inside the full report view. Use report identity to reset the page when changing reports. Retain the legacy summary when present and keep the API schema unchanged.
3. Run `node --test 'supporting files/testing/unit/test_report_view.mjs'` and pinned pytest for test_stage5_reports_history.py and test_history_pagination.py. Check the production build in the final candidate.
4. Remove the view block and regression checks to roll back. Existing SQLite reports and export data require no migration.

