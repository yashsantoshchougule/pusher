# RL-06 — Test the redesigned UI with the updated backend

Must Fix. Second issue in the current release backlog. Prerequisite [RL-05](RL-05-refresh-python-lockfile.md) passed.

## Execution prompt

Verify that the redesigned interface and current backend work together through the normal offline entry point. Use a disposable source copy with locked Python and Node dependencies, no project `.env`, and a fresh SQLite database. Keep both services and the test destination on loopback. Start the actual development launcher with `--offline`.

1. Verify the built-in sandbox in the browser. Use a small virtual-user count and short duration. Start from the dashboard, observe live metrics updating, then stop the run through the UI.
2. Confirm the run appears in history with the expected stop outcome. Open its report, download the PDF through its normal control, and check the output starts with a PDF header. Where applicable, confirm the browser's WebSocket connection and avoid any live external service calls.
3. Run the existing backend and frontend regression suites and production build from the same source snapshot. Use scratch data. Record failures and handle them before completion. Preserve unrelated work already in the checkout.
4. Record the outcome locally. Publication of the reviewed changes and hosted staging checks remain separate.

## Verification result

Resolved. `uv sync --locked --python <Python 3.12.14>` and `npm ci --prefix frontend --no-audit --no-fund` passed in the disposable checkout. `node frontend/scripts/dev-full.mjs --offline` started the actual app without credentials. On an alternate frontend port, the initial browser POST was denied because its origin was absent from `ALLOWED_ORIGINS`. The retry configured exactly the loopback browser origin and the loopback backend sandbox target. The application’s origin policy remained unchanged.

- Verified the built-in sandbox, saved a 20-second Steady Crowd profile for one virtual user, and started the run through the dashboard. Live throughput showed 567 requests per second during the short run. The backend accepted the browser's telemetry WebSocket.
- The Stop button ended the run. Test History showed `MANUAL ABORT` and 712 completed requests. Opened the same report and downloaded a 4,374-byte PDF starting with `%PDF-1.4`.
- `python -B -m pytest -q -p no:cacheprovider --tb=short` passed **232 tests** with 20 deprecation warnings using the freshly installed packages. The full Node suite passed **98 tests**, all **10 clock checks** passed, and `npm run build --prefix frontend` succeeded.

The published revision and hosted environment still need their own verification.
