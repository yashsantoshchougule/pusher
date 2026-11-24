# R06 The guard changes who the app thinks is calling

Must Fix. [Pusher Remediation — Remaining Issues](https://docs.google.com/document/d/1RpVDZM22lKwMj5eGugDi6j5t_-obO1TfsMldBH5kJQI/edit?usp=drivesdk)

The generated FastAPI middleware rewrites caller data before route dependencies run. The previous test asserted the mutation on an unprotected echo route. Limit the artifact to registering the ownership route in FastAPI, Starlette, and Flask. Preserve ordinary HTTP credentials and client attribution. Remove guard-based traffic exemptions from the controller, workers, and operator guidance.

1. Issue an ownership-only artifact and store its exact delivered SHA-256. Authenticate the fresh challenge and bind it to the issued origin, Guard ID, digest, and host tag with a distinct ownership purpose. Require the new digest for verification and execution. Show that old installations need replacement through the existing kill and regenerate flow. Preserve the current lifetime, device binding, and sandbox checks.
2. Mount the generated file in an isolated app with real authentication dependencies. Check denial, least-privilege permissions, ordinary bearer forwarding, and rate limits with fixed client identity. Check exact expiry, one-character tampering, and rejected wrong or stale challenge replies. Use the existing Stage 1 and outbound-target-policy tests and a scratch SQLite database.
3. Update installer and staging guidance. Existing generated files have to be replaced on their hosts. Review the digest out of band before installing the Python file. Run `uv run --locked python -m pytest` on the focused test files with mocked outbound HTTP.
