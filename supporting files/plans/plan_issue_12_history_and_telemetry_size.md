# Issue 12 — History and telemetry size

- Fetch owner-scoped run summaries with a stable timestamp and ID cursor. Default to 25 rows and cap requests at 100. Keep scorecards based on the whole filtered result and keep full details on report and export endpoints.
- Keep history out of polling and telemetry frames. Refresh summaries after completion and expose a load-more action. Fetch the complete report when the reports view opens.
- Limit new runs to at most 3,600 time-series buckets using the requested duration to choose the sampling interval. Preserve previous run detail without rewriting stored reports. Verify long-running and tied-timestamp cases.
