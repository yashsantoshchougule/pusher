# Pusher 🚀

> **A high-speed, safe, and 100% free website load testing engine designed for real-time performance insights without cloud bills.**

---

## 🌟 What is Pusher?

**Pusher** is an open-source, asynchronous website load testing tool for developers and engineering teams. It simulates concurrent virtual users against your web applications to identify bottlenecks and measure whole-run p95 latency and error rates.

Pusher's offline sandbox runs locally without cloud credentials. Its default 500 MB engine budget models up to 2,250 virtual users, subject to host and target limits. Measure actual memory use and throughput on the intended host before using that number as a capacity estimate.

---

## ⚡ Key Highlights & Safety Features

- 🛑 **Mandatory Target Verification**: Prove ownership of a live target with the downloadable Pusher Guard.
- 🛡️ **48-Hour Pusher Guard**:
  - An ownership verification route for FastAPI, Starlette, and Flask. Target requests use the app's normal authentication and rate limits.
  - **3/Day Rate Limiter**: Enforces a strict quota of at most 3 guard files per 24-hour rolling window (`HTTP 429 Too Many Requests`).
  - **Permanent Revocation**: Revoke the existing Guard before generating another. Pusher rejects revoked IDs.
- ⚡ **3 Automatic Safety Circuit Breakers**:
  1. *Crash Breaker*: Stops on five consecutive 5xx responses or a rolling five-second 5xx ratio over the configured limit (maximum 25%, with at least 20 responses).
  2. *Firewall Breaker*: Stops on three HTTP 429 responses within three seconds or an HTTP 403 with a recognized firewall signature.
  3. *Latency Breaker*: Stops when rolling p95 exceeds the configured ceiling (maximum 8 seconds) or the timeout rate exceeds 30%, with at least 20 completed requests in the window. Each request has a five-second deadline by default.
- 🔴 **Emergency Stop**: Cancels active workers, drains requests, and closes the run's HTTP client before allowing another run. Stop latency depends on the host and connection and must be measured separately.
- 💻 **Offline sandbox (`PUSHER_MODE=local_dev`)**: Use the built-in loopback target for a local smoke check. A separate mock server under the testing directory simulates HTTP 5xx and 429 responses.

---

## 📁 Repository Structure

### Install and run

Use Python 3.12.14 with `uv` and Node.js 24. The backend and test dependencies are locked in `uv.lock`.

```powershell
uv sync --locked
npm ci --prefix frontend
```

If `uv` cannot discover Python 3.12.14, install that version and run `uv sync --locked --python <path-to-python>`.

For the offline sandbox, run the backend on loopback and start Vite in a separate terminal.

```powershell
$env:PUSHER_MODE = 'local_dev'
$env:PUSHER_OFFLINE_DEV = 'true'
uv run --locked python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```powershell
npm run dev --prefix frontend
```

Open `http://127.0.0.1:3000/`, choose **Continue offline**, and verify `http://127.0.0.1:8000/api/sandbox/target` with Sandbox Simulation enabled.

For shared use, set `PUSHER_MODE=production` and `PUSHER_OFFLINE_DEV=false`. Set the backend's Supabase values using the root `.env.example` as a reference. Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` for the same project before building the frontend. Missing frontend settings disable cloud sign-in. Enable the intended providers in Supabase and allow the deployed frontend root URL in the redirect settings. Keep backend service credentials out of the frontend.

```powershell
uv run --locked python -m pytest
node --test (Get-ChildItem -LiteralPath 'supporting files/testing/unit' -Filter 'test_*.mjs' | ForEach-Object FullName)
node 'supporting files/testing/unit/test_time_mapping.cjs'
uv run --locked python 'supporting files/testing/verification/check_local_sandbox.py'
npm run build --prefix frontend
```

```
pusher/
├── backend/                             # Fast asynchronous Python backend (FastAPI, asyncio)
├── frontend/                            # React + Vite + Tailwind CSS dashboard & live charts
├── supporting files/
│   ├── rules/                           # Strict architecture, safety, and team guidelines
│   │   ├── architecture_and_standards.md# System architecture, features, and standards
│   │   ├── memory_management.md         # RAM budget rules (<500MB default for 2,250 VUs, scalable)
│   │   ├── safety_limits.md             # 3 circuit breakers & SSRF defense
│   │   ├── target_verification.md       # DNS & 2-in-1 Pusher Guard verification
│   │   ├── github_workflow.md           # Git rules & AI safety constraints
│   │   └── team_collaboration.md        # Team collaboration & agile development standards
│   ├── plans/                           # Architecture blueprints & technical design plans
│   │   ├── README.md                    # Plan index and naming conventions
│   │   └── plan_*.md                    # Descriptive feature and implementation plans
│   └── testing/                         # All test scripts, benchmarks, and mock servers
│       ├── mocks/                       # Mock target server (200 OK, 500 crash, 429 WAF)
│       ├── prototypes/                  # Engine prototypes and validation scripts
│       ├── benchmarks/                  # Memory & throughput benchmark scripts
│       └── unit/                        # Unit tests for verification and safety logic
└── README.md
```

---

### Saved journeys

Saved journeys retain endpoint paths, step settings, recognized content types, and extracted-variable header templates such as `Bearer {{token}}`. Query strings, request bodies, and other header values stay in the current tab and must be supplied again after reopening a saved journey. Keep credentials out of step names and path segments.

Main target queries also stay in the current tab. Re-enter them after reopening, or verify the URL without the query to clear the requirement for single-target runs. Journey steps supply their own queries.

If the database predates this change, stop the backend and select the intended `PUSHER_DB_PATH` before running the following maintenance command. It removes old request inputs, target and journey step queries from reports, and dry-run error text, compacts the database, and preserves the templates. Treat older database backups as sensitive and rotate any previously saved credentials.

```powershell
uv run --locked python -c 'from backend.core.database import scrub_legacy_journey_inputs; scrub_legacy_journey_inputs()'
```

## 📖 Project Documentation & Rules

All core technical specifications and collaboration guidelines are organized inside `supporting files/rules/`:

1. [Architecture & Standards](supporting%20files/rules/architecture_and_standards.md) — Tech stack, system flowcharts, and 13 core features.
2. [Target Verification](supporting%20files/rules/target_verification.md) — Origin checks, Guard ownership proof, and loopback sandbox setup.
3. [Safety Limits & Breakers](supporting%20files/rules/safety_limits.md) — Circuit breakers, emergency stop, and planned safety features.
4. [Memory Management](supporting%20files/rules/memory_management.md) — Zero-leak streaming, circular metrics buffers, and RAM profiling.
5. [GitHub Workflow](supporting%20files/rules/github_workflow.md) — Branching strategy, manual git rules, and AI safety boundaries.
6. [Team Collaboration](supporting%20files/rules/team_collaboration.md) — Modular subsystems, flexible task ownership, and API contracts.

---

## 👥 Modular Subsystems & Flexible Roles

The browser uses same-origin `/api` requests. Vite forwards HTTP and WebSocket traffic to `http://127.0.0.1:8000` in development. Set `PUSHER_DEV_API_ORIGIN` in the Vite process environment if the backend uses a different port. In a shared deployment, serve the frontend and proxy `/api` on the same HTTPS origin. Forward WebSocket upgrades for `/api/load/ws`, preserve the public Host header, and keep offline mode disabled.

- **Backend & Engine Subsystem**: Fast async socket pool, domain verifier, Pusher Guard generator, circuit breakers.
- **Frontend UI Subsystem**: Live dashboard, Chart.js telemetry, Emergency Stop button, verification wizard.
- **Testing & Quality Subsystem**: Standalone mock target server, prototypes, benchmarks, and unit tests.

---

## 🔒 Safety & Ethics Notice

Pusher is strictly intended for **authorized testing on domains and servers that you own or have explicit written permission to test**. Testing unauthorized third-party infrastructure is strictly blocked by built-in domain ownership verification and SSRF IP filters.
