# TS-03 — The user limit can be misleading

Must Fix · [Traffic Setup issue index](https://docs.google.com/document/d/15fP-9iPt46nczKeWkGzde4FS7xoSMYmz74HyC2JiBeo/edit?usp=drivesdk)

## Implementation prompt

Show the effective user limit given the operator's RAM setting and the engine's actual connection cap. The current page estimates the cap from RAM alone, and its descriptor percentage uses a synthetic formula. The engine clamps worker concurrency to its real connection cap.

1. Expose the engine's connection and requested-user caps through the additive system limits response. Reuse the same backend constants and cap function used by start. Preserve the existing engine thresholds.
2. Compute the effective maximum from the server's RAM model, the host budget, and the engine cap. Use it for presets and inputs, and replace the made-up descriptor percentage. Show unavailable values explicitly. Block a Traffic Setup launch when the current profile exceeds the effective limit.
3. Add a backend regression for a stubbed connection cap and dashboard/view regressions for preset limits, a saved value above the cap, and unknown limits. Run the targeted tests for system limits, load start and observed concurrency.

The endpoint addition is compatible with existing consumers. No migration or change to host safety caps is needed.

## Verification

Seven frontend and 40 backend tests passed with synthetic limit fixtures. [Drive report](https://docs.google.com/document/d/150p3EW5eczbjIOL3FptH1L1psSarwqh1kKlPRLW_E7A/edit?usp=drivesdk)

```powershell
node --test 'supporting files/testing/unit/test_traffic_setup_view.mjs' 'supporting files/testing/unit/test_traffic_dashboard.mjs'
python -B -m pytest -q -p no:cacheprovider 'supporting files/testing/unit/test_stage1_backend.py' 'supporting files/testing/unit/test_stage2_load_engine.py' 'supporting files/testing/unit/test_peak_concurrency.py'
```
