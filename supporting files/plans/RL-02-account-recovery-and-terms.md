# RL-02 — Finish account recovery and Terms

Must Fix, source item 2. [Release readiness index](https://docs.google.com/document/d/1VbRL-9GJ90Pq6VpJdidtVzftJS3Ad7kd5cq9OaIYt9g/edit)

The auth form links to two fragments with no implementation. The normal App session handler would also route a Supabase recovery session into the dashboard.

1. Route the reset request and callback at /auth/forgot and /auth/recovery. Use the same configured Supabase project. Keep the callback client session in memory and subscribe to PASSWORD_RECOVERY as soon as it is created. Show the form only for a valid recovery event. The normal application session handler does not mount on either route.
2. Confirm a reset request without revealing whether an account exists. Validate password confirmation, recheck the active user, then call updateUser. End the local recovery session and return to sign-in. Handle expired or reused links and cancellation. Use synthetic auth in local tests and require a disposable staging account for real delivery.
3. Serve a marked review draft at /terms. Link to it from signup and require the unchecked native checkbox for email and OAuth signup actions. Approved wording is a release gate. Existing login stays available.
4. Run focused Node auth and view checks, the production build, and a localhost readback of all three routes. Record hosted redirect and email checks as pending until staging is available.

## Fallback callback verification

A callback returning to the app root with a recovery marker previously instantiated the normal persistent Supabase client. The regression reproduced this before the fix. The client now detects the recovery route or marker before the SDK reads the credentials, uses the in-memory client, and opens the recovery view. The marker alone never permits a password update. The provider must still emit a valid recovery event.

The 15 focused Node tests passed. Chrome opened an invalid fallback URL at the app root, showed the invalid-link view at the dedicated recovery route, and offered a working link to the reset request form. The Terms draft also rendered. No account action was performed in Chrome.
