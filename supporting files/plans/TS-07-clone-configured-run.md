# TS-07 — Clone uses the wrong user count

Should Fix · [Traffic Setup issue index](https://docs.google.com/document/d/15fP-9iPt46nczKeWkGzde4FS7xoSMYmz74HyC2JiBeo/edit?usp=drivesdk)

## Implementation prompt

When the operator clones a history record, restore the requested user count and configured duration. History includes target_vus, peak_vus, and duration_sec. The Clone handler currently reads the observed peak and falls back to a made-up count.

1. Read the configured target and planned duration from the history summary, accepting the existing duration alias for older records. Normalize the stored traffic mode. Keep current values for fields that cannot be recovered and tell the operator.
2. Apply the current effective user limit when it is known, explicitly report any adjustment, and keep the original report intact. Place the values in the Traffic Setup draft for review and normal save.
3. Add integration tests for an interrupted run whose peak differs from its target, a run above current capacity and a legacy record missing the planned user count. Run focused dashboard and history tests. Finish with the entire isolated test suite, production build and local sandbox check.

The active verified target and unrelated profile options remain in their current context. No storage changes are needed.

## Verification

The full runs passed 169 backend and 51 frontend tests. The frontend production build ran with a clean temporary output directory. The sandbox smoke check passed with a temporary database and loopback traffic. The backend tests blocked unmocked HTTP transports. A live deployment, third-party WAF behavior and capacity load were outside the checks. [Drive report](https://docs.google.com/document/d/1i7Y2LHbLScdFMHeLKH8pfx9-9A5ed2kkB7ssWgXnmK8/edit?usp=drivesdk)

```powershell
python -B -m pytest -q -p no:cacheprovider --tb=short
node --test (Get-ChildItem -LiteralPath 'supporting files/testing/unit' -Filter 'test_*.mjs' | ForEach-Object FullName)
python -B 'supporting files/testing/verification/check_local_sandbox.py'
npm --prefix frontend run build -- --outDir (Join-Path ([IO.Path]::GetTempPath()) ('pusher-traffic-build-' + [guid]::NewGuid().ToString('N')))
```
