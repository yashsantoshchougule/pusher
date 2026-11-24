# TS-01 — The WAF switch does nothing

Must Fix, first in the [Traffic Setup issue index](https://docs.google.com/document/d/15fP-9iPt46nczKeWkGzde4FS7xoSMYmz74HyC2JiBeo/edit).

## Implementation prompt

Make Traffic Setup accurately describe Pusher's automatic stops. The WAF switch only changes local React state. The start API does not receive it, and the engine applies the same brakes in both worker types. The adjustable error percentage counts server errors (5xx). Rate-limit and firewall responses have separate rules.

1. Replace the switch with a clearly labeled always-on notice. Remove its unused state and props, and align the dashboard summary wording.
2. Label the adjustable value as a rolling server-error percentage and explain the minimum sample count and window. Explain that confirmed firewall blocks and repeated rate limits stop the run independently.
3. Add a static view regression under `supporting files/testing/unit` that checks the labels and confirms there is no switch. Run `node --test "supporting files/testing/unit/test_traffic_setup_view.mjs"` and the existing isolated `test_automatic_brakes.py`.

Keep the actual brake rules, API, and persisted settings intact. Rollback is limited to the UI and its regression.

## Verification

The new UI case failed before the fix. Afterward, 7 frontend and 6 backend tests passed. [Drive report](https://docs.google.com/document/d/1p4El0Q-vhTnwdfXWLCvidWngSkZ27-4KDSqSqfiZqNM/edit?usp=drivesdk)

```powershell
node --test 'supporting files/testing/unit/test_traffic_setup_view.mjs' 'supporting files/testing/unit/test_run_monitor.mjs'
python -B -m pytest -q -p no:cacheprovider 'supporting files/testing/unit/test_automatic_brakes.py'
```
