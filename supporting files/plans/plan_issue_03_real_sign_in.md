# Issue 03 — Real sign-in

- Route email sign-up and password sign-in through Supabase. Wait for the provider result and handle confirmation-required sign-up without entering the dashboard.
- Route Google and GitHub through Supabase OAuth. Exchange the callback using the SDK and confirm the session via the backend before rendering protected views. Show callback cancellations and missing configuration without creating a local session.
- Preserve explicit offline access from issue 02 and clear legacy fabricated session markers. Use provider sign-out for account switching. Remove the token-free Google provisioning route and SDK script from the active flow.
- Test the provider interface with mocked auth outcomes, check the removed provisioning route and the existing operator tests, and build the frontend.
