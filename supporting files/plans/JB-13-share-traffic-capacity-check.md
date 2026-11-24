# JB-13 — Use the same user limit as Traffic Setup

Must Fix. Second finding in the API Builder follow-up review. The [Journey Builder audit index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit) tracks the preceding issues. Drive access is currently unavailable, so the chat finding is the source for this prompt.

## Implementation prompt

The API Builder's Save & Launch can request more users than Traffic Setup permits. The mocked review gave the dashboard a worker cap of 80 and a 100-user profile. Traffic Setup reported the limit, while the Builder saved and sent a start request.

1. Reuse the dashboard's existing profile readiness, host RAM budget and effective worker-cap checks in the Builder's launch blocker. Show the same reason and disable Save & Launch before it sends any request.
2. Keep saving a journey draft independent of traffic capacity. Keep the server-side engine protections and the current default settings.
3. Test an over-cap profile, a profile at the limit, missing hardware data and a host RAM budget violation. Compare the actual blockers for both views. Use the existing mocked dashboard and view fixtures.
4. Run the focused Builder and Traffic Setup suites, then the full frontend suite, isolated backend suite and production build.

The frontend uses the existing system limits response. There is no API or storage migration.

## Resolution

**How it occurred.** The Builder used the engine's run status to enable its launch action. Traffic Setup also considered the user's resource settings and the engine worker limit.

**How it was solved.** Both views use the same profile-readiness checks and capacity calculation. The Builder shows the reason before sending a save or start request.

**Testing.** Before the change, the worker-cap, host-RAM, and unavailable-hardware regressions each sent both requests. All three now block both requests. A verified run at the worker limit still starts after a successful save.

```powershell
node --test 'supporting files/testing/unit/test_journey_builder.mjs' 'supporting files/testing/unit/test_journey_launch.mjs' 'supporting files/testing/unit/test_traffic_dashboard.mjs'
node --test (Get-ChildItem -LiteralPath 'supporting files/testing/unit' -Filter 'test_*.mjs' | ForEach-Object FullName)
python -B -m pytest -q -p no:cacheprovider --tb=short
npm --prefix frontend run build -- --outDir (Join-Path ([IO.Path]::GetTempPath()) ('pusher-journey-build-' + [guid]::NewGuid().ToString('N')))
python -B 'supporting files/testing/verification/check_local_sandbox.py'
```

**Result.** Resolved locally. The focused frontend run passed 32 tests. The full frontend and isolated backend suites passed 70 and 181 tests. The production build and loopback sandbox check passed. The isolated Python run used the pinned environment, temporary databases and blocked unmocked outbound HTTP. Live targets were outside verification.

The report was published and verified after access to the original audit folder was restored. [Drive report](https://docs.google.com/document/d/1PME0LyLgDezRqMEAEdpjtjknWVtXqQsiU4Lb6APhF-o/edit?usp=drivesdk)
