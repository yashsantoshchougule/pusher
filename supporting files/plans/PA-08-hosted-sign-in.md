# PA-08 — Verify hosted Supabase sign-in

Priority: Deployment Verification

Master: https://docs.google.com/document/d/1J9sPxjf_nf7PTuI4aV27e3jL_5rZ59tQ5bM4b3ZOEAs/edit?usp=drivesdk

## Task prompt

Verify real hosted signup, confirmation, Google and GitHub sign-in, backend session binding, owner isolation, and sign-out on a staging deployment with the same explicit Supabase project configured on both tiers. Use disposable test accounts and keep credentials and tokens out of results. Verify the selected Google account is permitted by the OAuth audience before testing.

## Available evidence and dependency

LoginPage.jsx delegates to the configured Supabase SDK. App.jsx gates the dashboard on the same-origin session response. PA-01 removes implicit project selection. Local auth fixtures can verify client contracts and backend enforcement. The repository exposes no approved staging URL or designated test identities for hosted sign-in. The earlier Google org_internal result described a provider-side deployment setting.

## Execution and acceptance

1. Run `node --test 'supporting files/testing/unit/test_sign_in.mjs'` and pinned pytest for test_backend_auth.py and test_operator_access.py.
2. When a staging release and accounts are available, confirm signup email redirects back, correct login produces a backend-verified owner, both configured providers return through the staging callback, and sign-out leaves a protected request unauthenticated. Confirm sign-in from a second test account leaves the first account's records private.
3. Track hosted results independently. Keep the task blocked if any required provider cannot be verified. No application or provider configuration changes are needed for the local verification.

