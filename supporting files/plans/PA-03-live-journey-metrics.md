# PA-03 — Show measured live journey step metrics

Priority: Must Fix

Master: https://docs.google.com/document/d/1J9sPxjf_nf7PTuI4aV27e3jL_5rZ59tQ5bM4b3ZOEAs/edit?usp=drivesdk

## Task prompt

Correct the dashboard's live per-step journey table. Display the requests, passes and failures reported by the current engine, label its existing latency measurement as average, and show unavailable before a step has any measured requests. Keep genuine zero counts and a measured zero latency. Scope the change to the live table. Archived progression is PA-05.

## Verified baseline and scope

load_engine.py initializes step_metrics and updates requests, passed, failed, avg_latency_ms, and last_status. DashboardPage passes step_metrics from the common HTTP/WebSocket status path to OverviewBoxes.jsx. The table reads total_requests, passed_requests, failed_requests, and p95_latency_ms, so real data renders as zeros.

## Implementation and verification

1. Add a render regression with synthetic live rows in supporting files/testing/unit/test_report_view.mjs. Assert the actual cell values and header, a zero-count unmeasured row, and a measured zero.
2. Replace the table cells with the existing backend field names and label the recorded average. Keep the server contract and status reconciliation unchanged.
3. Run `node --test 'supporting files/testing/unit/test_report_view.mjs' 'supporting files/testing/unit/test_telemetry.mjs' 'supporting files/testing/unit/test_run_monitor.mjs'`. Run the existing Python scheduled-journey tests with the locked interpreter and a frontend build in release verification.
4. Rollback consists of reverting the table and its focused tests. No migration or dependency changes are required.

