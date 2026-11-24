# JB-09 — Dry-run controls and results are incomplete

Should Fix · [API Journey Builder issue index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit?usp=drivesdk)

## Implementation prompt

Expose a safe Stop for the active dry run and report its outcome accurately. The existing generic Stop can affect a scheduled load run, so the Builder needs an owner-scoped stop for the identified dry run. The card currently conflates cancellation with failure, does not show step errors, and measures only completed step time.

1. Give each Builder dry run an opaque ID. Register it with the authenticated owner and add a dedicated stop route that cancels only that matching request and waits for cleanup. Keep the existing general stop API compatible.
2. Wire the Builder's Stop button to that ID. Protect against duplicate clicks, keep the button available after failed stop, and avoid reporting an unrelated run as stopped.
3. Measure wall-clock elapsed time, distinguish cancelled results, and display returned per-step errors. Keep partial outcomes and sanitized history.
4. Verify ownership, wrong ID, no effect on a scheduled run, late cancellation, timeout duration and cleanup using fake clocks and HTTP mocks. Test the real frontend handler and result rendering.

## Verification

11 backend dry-run, authorization and Stop tests plus 17 Node builder, view and monitor tests passed. Synthetic clocks verified elapsed time and cleanup. [Drive report](https://docs.google.com/document/d/1s3Dc9guBgPY7YMRMxvZTHMqnUQ9UG43PJxfNrugZAoE/edit?usp=drivesdk)
