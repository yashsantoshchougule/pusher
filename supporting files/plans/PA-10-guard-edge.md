# PA-10 — Verify Flask Guard and live edge behavior

Priority: Deployment Verification

Master: https://docs.google.com/document/d/1J9sPxjf_nf7PTuI4aV27e3jL_5rZ59tQ5bM4b3ZOEAs/edit?usp=drivesdk

## Task prompt

Verify the current generated Python Guard mounts on Flask and leaves the example target's authentication, authorization, CSRF enforcement, audit identity and rate limits intact. Verify expiry and the controller's normal ownership handshake with synthetic data. For the edge portion, run the existing defensive WAF tests and preserve the distinction between stubbed responses and a real firewall deployment.

## Verified baseline and dependencies

target_service.py generates one ownership route for FastAPI, Starlette, or Flask. Existing TestClient tests exercise the first two adapters. Flask is a target-framework dependency outside Pusher's runtime lockfile. There is no approved live Flask/WAF staging endpoint or edge config in the checkout.

## Implementation and verification

1. Install Flask into a scratch path solely for the optional target verification script. Keep Pusher's runtime dependencies and source unchanged.
2. Add a no-network verification script in supporting files/testing/verification. Generate a fresh artifact under disposable storage, mount it on Flask through setup_pusher_guard, feed actual Flask responses to the controller via HTTPX MockTransport, and verify ordinary protected routes, invalid challenges and exact expiry.
3. Run the script using the locked Pusher Python plus the isolated Flask path. Run existing guard integrity, application preservation, WAF probe and safety brake checks.
4. Production acceptance requires an authorized Flask app and actual edge configuration. Recheck the correct verified origin and ordinary auth behavior through the deployed edge, collect only bounded diagnostic evidence, and leave the deployed check blocked until that evidence exists.

