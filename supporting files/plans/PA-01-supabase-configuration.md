# PA-01 — Require explicit Supabase configuration

Priority: Must Fix

Master: https://docs.google.com/document/d/1J9sPxjf_nf7PTuI4aV27e3jL_5rZ59tQ5bM4b3ZOEAs/edit?usp=drivesdk

## Task prompt

Make cloud sign-in an explicit deployment choice. Use the current Supabase URL and browser key variables as a pair. If either is absent or blank, do not construct the SDK client or contact any provider. Show an actionable message as soon as the login screen opens. Keep Continue offline tied to the existing backend-issued offline operator and retain normal email, Google, GitHub, and server session checks when configured.

## Verified baseline and scope

The audited Vite module supplied both URL and browser key defaults and called createClient unconditionally. App.jsx and operatorApi.js already accept a null client for a same-origin session check. LoginPage.jsx is the sign-in entry point. Apply the change in the initializer and login screen, with local sign-out handled by the existing App flow. Leave backend authentication and provider projects untouched.

## Implementation

1. Test the actual Vite initialization module with an injected environment and SDK spy. Show that missing configuration currently creates a client.
2. Remove bundled defaults. Trim both values and create the client only with both inputs. Surface a configuration error for invalid SDK initialization as well.
3. Display the configuration error in the login UI and suppress cloud sign-in controls while unconfigured. Keep the existing offline action independent of client availability.
4. Verify the focused Node tests and the production build. If a rollout needs reversal, revert the scoped UI and initializer edits together. Deployments must explicitly supply the same Supabase project in frontend and backend settings.

## Acceptance and commands

- Missing both inputs, either missing input, and whitespace-only inputs yield a null client, a clear setup message, and zero SDK calls.
- Explicit settings pass through unchanged except for surrounding whitespace. A malformed URL reported by the SDK leaves the offline path usable.
- Run `node --test 'supporting files/testing/unit/test_sign_in.mjs'` and build Vite with a temporary output directory. Real provider credentials and hosted OAuth remain staging verification.

