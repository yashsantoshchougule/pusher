# VT-04 — Test Cross-Device Block permanently revokes the current Guard

Should Fix, fourth finding in the [Verify Target issue index](https://docs.google.com/document/d/1XKs8rqWzChBeCU9trm5WjBJDnI2h8Hj29FfzIDciZI0/edit).

## Implementation prompt

Remove the cross-device test from the Verify Target page and remove its Dashboard handler. The current button uses the active Guard and invokes a real revocation path. The action looks like a routine test and only explains its consequences in a tooltip. Keep explicit Kill ID and all backend enforcement intact.

1. Remove the test button, its prop and the one Dashboard caller. Keep the device-mismatch notice for genuine server-reported revocations.
2. Keep the manual Kill ID control and label its permanent effect. Correct the nearby claim that generating a file automatically replaces an existing Guard to match the kill-first rule.
3. Add a static render regression under `supporting files/testing/unit` for an active Guard. Confirm that the deliberate revocation control remains and the destructive test is absent. Reuse the view fixture and run the nearby dashboard tests plus backend guard and status tests with a temporary database.

The public API and storage stay compatible. The test exercises rendered controls only.

## Verification

The rendered view regression failed before the fix. All six frontend tests and 30 backend tests passed afterward. [Drive resolution](https://docs.google.com/document/d/1gw4RvIj_NoRNM7VS0tG1pZ1mlB18BKNzQ4-mtmnb5Ws/edit)

```powershell
node --test 'supporting files/testing/unit/test_verify_target_view.mjs' 'supporting files/testing/unit/test_verify_target_dashboard.mjs'
python -B -m pytest -q -p no:cacheprovider 'supporting files/testing/unit/test_stage1_backend.py' 'supporting files/testing/unit/test_guard_deadline.py'
```
