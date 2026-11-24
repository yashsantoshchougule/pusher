# Issue 05 — Automatic brakes

- Apply the same response and timeout rules to both workers. Count consecutive 5xx responses and rolling 5xx ratios, detect three 429s within three seconds, and detect firewall-marked 403s from headers or a bounded response preview.
- Enforce the configured 2–10 second request deadline, including streamed responses. Evaluate rolling p95, timeout rate, and process memory. Route trips through the cancellation lifecycle from issue 04.
- Drive boundary cases with a fake clock and run both worker variants against a mocked client. Update the README to match the documented and tested thresholds.
