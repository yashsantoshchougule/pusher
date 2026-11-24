# TS-04 — Launch can look ready when it’s disabled

Must Fix · [Traffic Setup issue index](https://docs.google.com/document/d/15fP-9iPt46nczKeWkGzde4FS7xoSMYmz74HyC2JiBeo/edit?usp=drivesdk)

## Implementation prompt

Make the Launch action reflect the real run state. The button is disabled in several cases but still looks ready, and most start errors are routed to Verify Target even when the target is verified. A quick double click can attempt more than one start.

1. Derive a clear reason from verification, current-run status, save state and hardware limits. Apply the same reason to disabled styling and the action guard.
2. Lock start while its HTTP request is pending across launch entry points. Show the API error at the originating view, refresh run status after a conflict or connection loss, and allow a retry when it is safe. Preserve the existing target-verification prompt for an unverified selection.
3. Add mocked dashboard and view regressions for pending, busy and unavailable status, duplicate activation, server rejection and successful retry. Run the traffic, target, journey launch and run monitor tests.

The start endpoint, ownership checks and Stop lifecycle stay as implemented.

## Verification

All 27 frontend tests passed. The fixtures simulated status checks, duplicate clicks, start failure and retry. [Drive report](https://docs.google.com/document/d/1URmCK9uL_9j59D4mUoHYM7g6FgJBxd2lun5D-fspDEs/edit?usp=drivesdk)

```powershell
node --test 'supporting files/testing/unit/test_traffic_setup_view.mjs' 'supporting files/testing/unit/test_traffic_dashboard.mjs' 'supporting files/testing/unit/test_verify_target_dashboard.mjs' 'supporting files/testing/unit/test_run_monitor.mjs' 'supporting files/testing/unit/test_journey_launch.mjs'
```
