# Issue 08 — Telemetry fields

- Map concurrency, throughput, latency, errors, and discarded bytes from the live API contract through one frontend function. Use it for both polling and WebSockets.
- Initialize idle telemetry from the same mapping and remove fabricated fallback values from the simulated-spike handler. Surface a failed request as an error.
- Verify realistic metrics and legitimate zeros in frontend tests and build the application.
