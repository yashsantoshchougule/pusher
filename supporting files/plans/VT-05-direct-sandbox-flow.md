# VT-05 — Sandbox still shows Guard installation instructions

Should Fix, fifth finding in the [Verify Target issue index](https://docs.google.com/document/d/1XKs8rqWzChBeCU9trm5WjBJDnI2h8Hj29FfzIDciZI0/edit).

## Implementation prompt

Give the built-in sandbox a direct Verify Sandbox flow. The API can verify configured loopback sandbox targets without a Guard download. The page currently shows the public DNS, install and ownership challenge instructions in both modes and advertises sandbox even when the server disallows it.

1. Add the server-selected built-in sandbox URL to the authenticated target status in local development. Return null in production. Use the existing configured backend port and built-in sandbox policy.
2. Show the sandbox mode control only when the status exposes the option. Make it keyboard-accessible. When enabled, prefill the local URL or reuse an already verified sandbox, and keep the live draft available when switching back.
3. Show Verify Sandbox without the install or ownership challenge panels. Keep Kill ID available and explain when a live Guard must be revoked first. Continue sending requests to the existing verify endpoint and honor backend sandbox restrictions.
4. Extend the dashboard, view and Stage 1 tests. Verify local capability and production omission, default URL selection, guard-free verification without using a generation, restoration of the live draft, preservation of the live install UI, and retention of the manual kill action. Run all backend and frontend unit tests and the production build after the focused checks.

The status field is additive. The verification call still uses the existing endpoint and policy. No data migration is needed.

## Verification

The status and UI tests failed before the fix. Afterward, 37 focused backend tests and 11 focused frontend tests passed. The full isolated runs passed 167 backend tests and 34 frontend tests. The production build and loopback smoke check passed. [Drive resolution](https://docs.google.com/document/d/1kk7aAmjHwQqCNGMK122p8e2pFdBxUgpYmW7ZfcDA8ZQ/edit)

From the repository root with the pinned Python environment active:

```powershell
python -B -m pytest -q -p no:cacheprovider --tb=short
node --test (Get-ChildItem -LiteralPath 'supporting files/testing/unit' -Filter 'test_*.mjs' | ForEach-Object FullName)
python -B 'supporting files/testing/verification/check_local_sandbox.py'
```

The full backend run blocked unmocked outbound HTTP transports. The smoke check used loopback and a disposable SQLite database. The production build ran from `frontend` with a fresh temporary output directory. The suite reported deprecation warnings, and the frontend build reported a large chunk. Live Guard installation and third-party WAF behavior remain unverified.
