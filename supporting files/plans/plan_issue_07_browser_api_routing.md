# Issue 07 — Browser API routing

- Send dashboard, profile, session, and WAF requests to same-origin /api paths. Keep the telemetry WebSocket on the current page origin.
- Keep the Vite proxy for HTTP and WebSocket development traffic, with a loopback default. Document how a shared deployment forwards /api and WebSocket upgrades on the same origin.
- Run a proxy integration test with a loopback mock backend, including start headers, target status, and a telemetry upgrade. Verify the production build.
