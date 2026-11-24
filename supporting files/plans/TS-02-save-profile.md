# TS-02 — Save Profile can leave settings unsaved

Must Fix · [Traffic Setup issue index](https://docs.google.com/document/d/15fP-9iPt46nczKeWkGzde4FS7xoSMYmz74HyC2JiBeo/edit?usp=drivesdk)

## Implementation prompt

Make the two Traffic Setup actions wait for an acknowledged traffic-profile save. The existing setters post complete snapshots without waiting, discard HTTP and network errors, and can race. The Save Profile button only navigates. Keep autosave for existing users, and retain the same API shape.

1. Keep one draft snapshot and serialize the requests with an ordered writer. Compose successive edits from the current draft, ignore outstanding initial hydration once editing starts, and allow later saves after an error.
2. Use explicit Save Profile and Save & Launch handlers that wait for the latest snapshot, surface errors, and avoid navigating or starting on failure. Freeze form edits while the explicit save is pending. Keep shared profile RAM updates going through the same writer.
3. Add tests under supporting files/testing/unit for ordered writes, error recovery, edit-before-hydration, and refusal to launch or leave until success. Run the Node traffic tests and the backend persistence tests.

No storage migration is needed. On rollback restore the old handlers and remove the targeted regression files.

## Verification

The baseline Save button only navigated. Mocked ordered writes, failure and retry, and late hydration passed. The focused runs passed 11 frontend and 11 backend tests. [Drive report](https://docs.google.com/document/d/1PQZa3x0p5qBi94MgC_n6Y2N5vnvpdzktvsWFdLaPJ2Q/edit?usp=drivesdk)

```powershell
node --test 'supporting files/testing/unit/test_traffic_setup_view.mjs' 'supporting files/testing/unit/test_traffic_dashboard.mjs' 'supporting files/testing/unit/test_verify_target_dashboard.mjs'
python -B -m pytest -q -p no:cacheprovider 'supporting files/testing/unit/test_database_persistence.py' 'supporting files/testing/unit/test_operator_access.py'
```
