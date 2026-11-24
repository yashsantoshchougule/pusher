# TS-06 — The page doesn’t say what it will run

Should Fix · [Traffic Setup issue index](https://docs.google.com/document/d/15fP-9iPt46nczKeWkGzde4FS7xoSMYmz74HyC2JiBeo/edit?usp=drivesdk)

## Implementation prompt

Show what Traffic Setup will launch and restore the saved single-URL or journey selection. The page does not expose the mode and checks a run-state field that the journey endpoint never returns. Active-run telemetry currently overwrites the next-run preference.

1. Load journey configuration independently. Restore the saved selection and steps as separate fields, preserving any field edited while the request is pending. Keep private request fields in the browser.
2. Keep the current run's mode in telemetry and the next run's draft mode in the editor. Tell the operator which one Traffic Setup will launch and provide a link to API Journey Builder. Pause launch if the mode is unknown or a selected journey has no steps.
3. Test saved journey and single-URL launch payloads, late hydration with local edits, and telemetry isolation. Run the Node traffic, journey, target and run-monitor checks and the relevant backend journey tests.

Use the existing start payload, backend destination checks and saved journey API.

## Verification

The focused runs passed 31 frontend and 12 backend tests for both run types, local draft preservation, and journey controls. [Drive report](https://docs.google.com/document/d/1icHCnzhUxTPXt3FkNcA3xgrg-P0lJ-pwhT50KRnLKxw/edit?usp=drivesdk)

```powershell
node --test 'supporting files/testing/unit/test_traffic_setup_view.mjs' 'supporting files/testing/unit/test_traffic_dashboard.mjs' 'supporting files/testing/unit/test_verify_target_dashboard.mjs' 'supporting files/testing/unit/test_run_monitor.mjs' 'supporting files/testing/unit/test_journey_launch.mjs'
python -B -m pytest -q -p no:cacheprovider 'supporting files/testing/unit/test_stage4_api_journey.py' 'supporting files/testing/unit/test_journey_secret_storage.py' 'supporting files/testing/unit/test_dry_run_controls.py'
```
