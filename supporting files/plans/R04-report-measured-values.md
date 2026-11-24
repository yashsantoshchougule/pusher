# R04 Reports display fabricated latency values

Should Fix. [Pusher Recheck — Issue Index](https://docs.google.com/document/d/1ly_V4x7fTuRIa0-n818n-kPzQIt5Qcmrf8MFCynCq6o/edit)

The scorecard percentile table replaces actual zero and absent values with example numbers. The comparison view has the same issue and reads different field names from the API response.

1. In ReportsView render p95 from the report and show unavailable fields explicitly. Preserve numeric zero in both scorecard and comparisons. Use the comparison contract returned by report_service.py and show its verdict and summary. Display older measurement windows as labeled in R08.
2. On report selection and comparison failure avoid rendering metrics for another run. Keep current API and report exports unchanged.
3. Render actual React components in an isolated Node regression for a zero p95, a measured report, a legacy report, and missing results. Run node --test on test_report_view.mjs and rebuild Vite.

Reports keep their existing data. Percentiles that the API has never recorded appear as unavailable.
