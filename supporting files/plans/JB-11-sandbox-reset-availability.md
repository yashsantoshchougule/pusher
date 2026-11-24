# JB-11 — Reset Sandbox Defaults is shown in production

Should Fix · [API Journey Builder issue index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit?usp=drivesdk)

## Implementation prompt

Offer Reset Sandbox Defaults only when the server advertises a local sandbox. The audit confirmed that production exposes a button for a preset endpoint which returns 404. In local mode, it can erase the current draft without warning or overwrite edits made during a slow response.

1. Reuse the sandbox capability from the authenticated target status. Hide the button and guard the callback when unavailable.
2. Confirm before replacing an existing draft. While fetching, suppress duplicate reset requests. Apply the response only if the editor revision still matches.
3. Test production, a declined replacement, a late result after another edit, and successful local reset. Run the focused frontend regressions, full isolated suites, production build and local sandbox smoke check.
4. Reconcile all eleven prompts and verified Drive reports. Use a temporary database, mocked outbound HTTP and loopback for the final verification.

## Resolution

**Issue.** The Sandbox Defaults button appeared in production. In local development, the button could replace a draft without confirmation or discard edits made while the preset loaded.

**How it occurred.** The view rendered the control without checking server capabilities. The reset callback applied the response without checking whether the editor had changed.

**How it was solved.** The dashboard uses the local sandbox capability from target status. The button is hidden where the preset is unavailable. The callback confirms replacement, blocks duplicate requests, and checks the editor revision before applying the preset.

**Testing.** All 15 focused Builder and dry-run view checks passed. They cover a hidden control, cancelled replacement, an edit while the preset loads, repeat clicks, and successful reset.

```powershell
node --test 'supporting files/testing/unit/test_journey_builder.mjs' 'supporting files/testing/unit/test_dry_run_view.mjs'
```

**Result.** Resolved locally. The prior Drive access blocker cleared. The report was published and verified in the original audit folder. [Drive report](https://docs.google.com/document/d/1cYs7qCgiU1MfW6LBIK4bXVohxPPrf36XklNljtUimQs/edit?usp=drivesdk)

## Final regression checks

- Backend suite, 181 passed. The pinned Python environment used a temporary database and blocked unmocked HTTP transports.
- Frontend suite, 64 passed.
- Vite production build passed with a large bundle warning. The build output went to a fresh temporary directory.
- Local sandbox flow passed over loopback with a temporary SQLite database. It covered verification, journey save, dry run, scheduled run, history, and export.
- The scoped diff passed the whitespace check. A live target and third-party WAF were outside verification.

```powershell
python -B -m pytest -q -p no:cacheprovider --tb=short
node --test (Get-ChildItem -LiteralPath 'supporting files/testing/unit' -Filter 'test_*.mjs' | ForEach-Object FullName)
npm --prefix frontend run build -- --outDir (Join-Path ([IO.Path]::GetTempPath()) ('pusher-journey-build-' + [guid]::NewGuid().ToString('N')))
python -B 'supporting files/testing/verification/check_local_sandbox.py'
```
