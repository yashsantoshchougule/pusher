# RL-01 — Make local startup reliable

Must Fix, source item 1. [Release readiness index](https://docs.google.com/document/d/1VbRL-9GJ90Pq6VpJdidtVzftJS3Ad7kd5cq9OaIYt9g/edit)

The browser loads Vite on port 3000 even when the backend on port 8000 is unavailable. This produces an HTTP 500 for the proxied session check. Windows Application Control previously blocked the virtual environment's Python launcher, while its installed base interpreter worked.

1. Add a dependency-free Node 24 launcher behind `npm run dev:full --prefix frontend`. Use installed dependencies, default to loopback ports 3000 and 8000, and allow explicit alternative ports for isolated development.
2. Start the backend first using the synced Python environment. On Windows only, if the launcher cannot execute, probe the base interpreter from pyvenv.cfg and check its version and dependency imports before starting it.
3. Require Pusher's backend health response, frontend HTML, and the expected session response via Vite before printing readiness. The normal mode expects a Bearer 401 and explicit offline mode expects the offline identity.
4. Fail clearly on occupied ports, missing dependencies or child exit. Shut down only the children started by the launcher. Preserve the existing frontend-only command.
5. Add focused Node checks for port validation, Python fallback, proxy readiness, timeout, and child cleanup. Exercise real Windows cloud and offline startup with disposable databases and alternate loopback ports. Run the existing Vite proxy test.
