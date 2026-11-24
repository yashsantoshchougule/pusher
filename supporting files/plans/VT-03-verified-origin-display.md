# VT-03 — Changing the URL can leave the old Verified badge visible

Must Fix, third finding in the [Verify Target issue index](https://docs.google.com/document/d/1XKs8rqWzChBeCU9trm5WjBJDnI2h8Hj29FfzIDciZI0/edit).

## Implementation prompt

Only show a draft as verified and let it start a run when the active Guard covers its origin and mode. The review changed the draft host and still saw Verified. DashboardPage receives canonical target metadata but shares one boolean across the editable URL and mode. The backend independently checks normalized scheme, host and port, and sandbox mode.

1. Keep the server-confirmed target and mode together with the Guard status. Derive whether the current draft is covered from a safe origin comparison and matching mode. Treat invalid URLs as unverified. Keep same-origin path and runtime query edits permitted.
2. Use that derived result for the Verify Target badge and existing launch gate. Tell the user which origin the active Guard covers when the draft differs. Keep the active Guard and timer so the user can return to the covered URL or revoke it. Retain the existing status hydration and runtime query privacy behavior.
3. On a successful ownership response, use the submitted mode and update the draft URL only if the user has not edited it during verification.
4. Extend `test_verify_target_dashboard.mjs` to verify host, scheme, port and mode differences, equivalent origins, and refusal to launch an unmatched draft. Use mocked HTTP with no requests to a live target. Run the dashboard and target input tests plus the Vite production build.

No API changes or migration are needed. Roll back the origin helper, derived status and related tests together if required.

## Verification

Both new tests failed before the fix. All six tests in the target suites and the production build passed afterward. [Drive resolution](https://docs.google.com/document/d/1QRs7K-TQFe_rau3wDV90F5u1QXPuC6LyYEBW7qkY628/edit)

```powershell
node --test 'supporting files/testing/unit/test_verify_target_dashboard.mjs' 'supporting files/testing/unit/test_target_input.mjs'
```
