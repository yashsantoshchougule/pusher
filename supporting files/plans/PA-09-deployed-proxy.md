# PA-09 — Verify reverse proxy routing and WebSockets

Priority: Deployment Verification

Master: https://docs.google.com/document/d/1J9sPxjf_nf7PTuI4aV27e3jL_5rZ59tQ5bM4b3ZOEAs/edit?usp=drivesdk

## Task prompt

Verify that the staging HTTPS proxy serves the frontend and routes /api HTTP requests and WebSocket upgrades on the same origin. Exercise authenticated start, telemetry, target status, and the active-run HTTP fallback. Keep the checks on a controlled staging sandbox and avoid editing deployment configuration during evidence collection.

## Verified baseline and dependency

Vite forwards HTTP and WebSocket traffic using one /api proxy rule. The frontend uses the public browser origin. load_router.py verifies WebSocket Origin against the public host and requires a session before telemetry. The checkout contains a loopback proxy fixture but no staging proxy config, executable, or endpoint for the deployed verification.

## Execution and acceptance

1. Run `node --test 'supporting files/testing/unit/test_browser_proxy.mjs' 'supporting files/testing/unit/test_run_monitor.mjs'` for same-origin routing, a local WebSocket upgrade and HTTP fallback.
2. In staging, verify the public TLS certificate and preserved Host header. Confirm a genuine authenticated WSS connection receives its first telemetry snapshot. Confirm unauthenticated telemetry sends no snapshot, and test reload/recovery with the test browser's socket unavailable.
3. Verify a bounded sandbox run, inspect narrow proxy/backend logs without tokens, and record the environment and result. Keep the task blocked until the actual deployed path passes.

