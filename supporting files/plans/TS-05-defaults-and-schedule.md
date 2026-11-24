# TS-05 — The defaults and preview don’t match the run

Should Fix · [Traffic Setup issue index](https://docs.google.com/document/d/15fP-9iPt46nczKeWkGzde4FS7xoSMYmz74HyC2JiBeo/edit?usp=drivesdk)

## Implementation prompt

Show the real selected duration and latency, and render the engine's actual traffic schedule. The default profile uses 30 seconds and 1,500 milliseconds. The current preset lists omit both. The preview is hardcoded and skips the rush warm-up and ramp steps.

1. Add the real defaults and show current values even for previously saved or cloned settings without a matching preset.
2. Expose the engine's schedule parameters with hardware limits. Use those parameters to show the active intervals and user counts. A short run should show only the phases it can reach. Include the engine's actual latency ceiling bound for old profiles.
3. Add view tests for selected defaults and schedule cutoffs and backend tests that cross-check the exposed schedule with the engine. Run the focused view, dashboard and engine tests.

The execution schedule and safety thresholds stay the same. The server response change is additive.

## Verification

The focused runs passed 13 frontend and 45 backend tests, including the server schedule and view boundary tests. [Drive report](https://docs.google.com/document/d/1uNj19POJ9fSqD6Po6rFBNg3xEIqMvn8zsZs5rtPNMYc/edit?usp=drivesdk)

```powershell
node --test 'supporting files/testing/unit/test_traffic_setup_view.mjs' 'supporting files/testing/unit/test_traffic_dashboard.mjs'
python -B -m pytest -q -p no:cacheprovider 'supporting files/testing/unit/test_stage1_backend.py' 'supporting files/testing/unit/test_stage2_load_engine.py' 'supporting files/testing/unit/test_automatic_brakes.py'
```
