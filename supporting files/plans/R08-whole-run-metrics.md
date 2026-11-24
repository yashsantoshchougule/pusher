# R08 The final report can hide earlier errors

Must Fix. [Pusher Remediation — Remaining Issues](https://docs.google.com/document/d/1RpVDZM22lKwMj5eGugDi6j5t_-obO1TfsMldBH5kJQI/edit)

The final scorecard copies the live one-second snapshot. If nine early requests fail and the last request passes, the archived error rate can show zero.

1. Record failed request counts and latency samples from both workers in the shared engine response handler. Reset counters every run. Compute nearest-rank p95 with a fixed histogram of 1 ms buckets through 60 seconds and a conservative overflow value. Keep live telemetry rolling.
2. Exclude the simulated stop exercise from measured request counters and latency. Persist a metric scope marker and identify legacy samples in the report. Expose missing metrics when no request completed, while preserving data in the existing SQLite schema and exports.
3. Run the new whole-run metric tests, history, Stage 2, Stage 3, Stage 5, and brakes tests on scratch SQLite. Verify the 90% case, nearest rank including zero, simulation, no samples, and legacy read compatibility.

This adds one SQLite column. Earlier reports retain their original values and display a scope notice.
