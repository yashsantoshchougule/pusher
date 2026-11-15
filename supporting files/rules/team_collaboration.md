# Team Collaboration & Development Standards

## 1. Overview & Collaboration Philosophy
This document defines how developers collaborate on **Pusher** to build a high-performance, beginner-friendly web load testing engine.

Whether working as a solo engineer or in a distributed team, maintaining strict modularity prevents merge conflicts, protects API stability between frontend and backend, and keeps load-testing benchmarks accurate without spending money on cloud servers.

Task distribution and branch assignments are managed flexibly by the developer or project lead based on active milestones, adhering to the standards outlined below.

---

## 2. Master Diagram: Git Feature Workflow & Local Mock Testing

```
========================================================================================
PART 1: GIT FEATURE BRANCH WORKFLOW (FEATURE BRANCHES -> PULL REQUEST -> MAIN)
========================================================================================

    DEVELOPER WORKSPACE                               TEAM REPOSITORY
  [ feature/<feature-name> ]                         [ origin/feature/<name> ]
  • Flexible task assignment                                 │
  • Modular subsystems (backend, frontend)                   │
  • Testing exclusively in supporting files/testing/        │ Manual commit & push
            │                                                ▼
            └─────────────────────────────────────► GitHub Pull Request
                                                    (Code Review & Automated Checks)
                                                               │
                                                               ▼
                                                         [ main Branch ]
                                                  (Always working, tested code)

========================================================================================
PART 2: LOCAL DEVELOPMENT & MOCK TARGET TESTING (PUSHER_MODE=local_dev)
========================================================================================

┌───────────────────────────────────────┐         Local Loopback / Network        ┌───────────────────────────────────────┐
│         PUSHER LOAD RUNNER            │         (localhost / LAN IP)            │          MOCK TARGET SERVER           │
│                                       │ ──────────────────────────────────────> │                                       │
│ • Pusher Web UI (React + Vite)        │       HTTP Load Traffic (Async I/O)     │ • mock_target_server.py               │
│ • FastAPI Backend (Python Async)      │                                         │ • Listens on 0.0.0.0:8080             │
│ • RAM kept < 250MB for 1,000 VUs      │ <────────────────────────────────────── │ • Returns 200 OK, 5xx, or 429 WAF     │
│ • PUSHER_MODE=local_dev               │          Live HTTP Responses            │ • Independent port or local host      │
└───────────────────────────────────────┘                                         └───────────────────────────────────────┘
```

---

## 3. The 6 Core Development Rules

### Rule 1: Modular Subsystems & Flexible Task Distribution
To prevent merge conflicts and maintain clean separation of concerns, the repository is organized into three decoupled subsystems:

1. **Backend & Engine Subsystem**:
   - `backend/core/` (Frozen Core: socket pools, streaming reader, queue lock, circuit breaker orchestration, contracts).
   - `backend/plugins/` (Scalable extensions: traffic modes, request builders, safety breakers, domain verifiers, diagnostic advisors).
   - `backend/api/` (REST endpoints and WebSocket live telemetry publisher).
2. **Frontend UI Subsystem**:
   - `frontend/src/core_ui/` (Always-on controls: Emergency Stop button, system health bar, network clients).
   - `frontend/src/features/` (Modular UI cards: verification wizard, traffic config panel, API tester drawer, live telemetry charts, diagnostic banners).
3. **Testing & Quality Subsystem**:
   - `supporting files/testing/` (Exclusive repository for mock target servers, async engine prototypes, memory benchmarks, and unit tests).

> **Flexible Ownership Rule**: Task distribution, file editing, and branch assignments are assigned flexibly by the developer or project lead. No files or directories are permanently locked to any single person. However, developers must coordinate before modifying cross-cutting interfaces (such as `contracts.py` or shared styles).

#### Shared Testing Rule:
* All test scripts, mock endpoints, prototypes, and benchmarks must stay strictly inside `supporting files/testing/`. No testing code is allowed in the project root or production source directories.

---

### Rule 2: The "API Contract First" Rule (Connecting Frontend & Backend)
Before implementing backend features or building frontend UI components, developers must agree on the exact data schema exchanged between `frontend/` and `backend/`.

> **FROZEN CORE CONTRACTS**: All REST request/response schemas and WebSocket telemetry frames are formally defined and locked inside **`backend/core/contracts.py`** using Pydantic models. Any change to a key name or field type must be coordinated before `contracts.py` is updated so frontend dashboards never break unexpectedly.

#### A. Standard REST Endpoints Contract:
1. `GET /api/v1/plugins` — Returns list of active traffic modes, request builders, and breakers from `backend/core/plugin_registry.py` so the React UI populates dropdowns and toggles dynamically.
2. `POST /api/v1/verify/dns` — Submits target domain to verify via DNS TXT record.
3. `POST /api/v1/verify/http` — Submits target domain to verify via static `/.well-known/pusher-challenge.txt`.
4. `POST /api/v1/verify/middleware` (or `GET /api/v1/verify/guard-template?lang=python|node`) — Returns the downloadable 2-in-1 `pusher_guard.py` (FastAPI/Flask) or `pusherGuard.js` (Express) file with verification token & HMAC bypass key embedded.
5. `POST /api/v1/test/start` — Starts load test with parameters `{ target_url, vus, duration_sec, mode }`. Returns `{ test_id, status }`.
6. `POST /api/v1/test/stop` — Instant Emergency Stop signal. Stops all tasks in `< 200ms`.
7. `GET /api/v1/test/status` — Checks current engine state (`IDLE`, `QUEUED`, `RUNNING`).

#### B. The 1-Second WebSocket / SSE Live Telemetry Contract:
Every second during an active test, the backend sends this exact JSON message to the frontend:

```json
{
  "test_id": "b1a2c3d4-e5f6-4a5b-9c8d-1234567890ab",
  "elapsed_seconds": 12,
  "active_vus": 25,
  "current_rps": 384.5,
  "latencies": {
    "p50_ms": 28.4,
    "p90_ms": 52.1,
    "p95_ms": 78.0,
    "p99_ms": 115.6
  },
  "status_counts": {
    "200": 380,
    "502": 4
  },
  "bytes_streamed": 1572864,
  "generator_health": {
    "loop_lag_ms": 3.2,
    "host_ram_mb": 45.2
  },
  "active_alerts": []
}
```

---

### Rule 3: Manual Git & Feature Branching Protocol
To guarantee complete human control and clean code history:
* **The AI assistant is 100% forbidden from executing `git commit`, `git merge`, `git rebase`, or `git push`.** All Git commands are typed manually by human developers.

```
       [ main Branch ] (Protected: Only tested, working code)
              ▲
              │ Pull Request (Review & Merge)
       ┌──────┴──────┐
       │             │
  feature/auth   feature/dashboard (Feature Branches)
```

#### Step-by-Step Feature Workflow:
1. **Create / Sync Branch with Main**:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/<feature-name>
   ```
2. **Inspect Changes**:
   ```bash
   git status
   git diff
   ```
3. **Stage Changes Explicitly**:
   Avoid `git add .` to prevent accidentally staging temporary logs or secrets:
   ```bash
   git add backend/
   # or
   git add frontend/
   # or
   git add "supporting files/testing/"
   ```
4. **Manual Descriptive Commit**:
   ```bash
   git commit -m "feat(backend): add consecutive 5xx error counter to circuit breaker"
   ```
5. **Push Feature Branch & Open PR**:
   ```bash
   git push origin feature/<feature-name>
   ```
   Open a Pull Request on GitHub to merge into `main` after review and test verification.

---

### Rule 4: Local Development & Mock Target Testing (`PUSHER_MODE=local_dev`)
Developers do not need live public domains, paid cloud accounts, or third-party DNS to develop and test Pusher.

#### The Local Mock Target Setup:
1. **Start Mock Target Server**:
   Start the standalone mock target server from `supporting files/testing/mocks/`:
   ```bash
   python "supporting files/testing/mocks/mock_target_server.py"
   ```
   This server listens on `0.0.0.0:8080` and provides simulated responses (fast 200 OK, crashing 500s, 429 rate limits, and latency spikes).
2. **Configure Pusher for Local Testing**:
   Ensure `PUSHER_MODE=local_dev` in your `.env` file. In this mode, Pusher automatically allows tests against local addresses (`localhost`, `127.0.0.1`, and private subnet IPs) without requiring DNS TXT records.
3. **Run Load Test**:
   Target `http://localhost:8080` (or `http://<local-ip>:8080` if running on another machine over the local network) from the Pusher UI.
4. **Result**: Realistic, non-blocking network testing with zero cloud costs, zero DNS delays, and zero external firewall interference.

---

### Rule 5: Shared Environment & Dependency Standards
To prevent "works on my machine" inconsistencies across development environments:
1. **Standard Runtime Versions**:
   * **Python**: Python 3.11+
   * **Node.js**: Node 18+ LTS
2. **Locking Dependencies Immediately**:
   * Whenever adding a Python package, immediately update `backend/requirements.txt`:
     ```bash
     pip freeze > backend/requirements.txt
     ```
   * Whenever adding an npm package, ensure it is saved in `frontend/package.json`:
     ```bash
     npm install <package> --save
     ```
3. **Environment Security**:
   * Never commit `.env`, `.env.local`, `node_modules/`, `venv/`, or log files to Git.
   * Maintain a clean, sanitized `.env.example` in the project root documenting all required configuration variables.

---

### Rule 6: AI Assistant Governance
When utilizing AI assistants for coding and refactoring:
1. **Context Loading**: Instruct the AI to read the rules in `supporting files/rules/` before writing or modifying code.
2. **Strict Prohibitions for AI**:
   * The AI is strictly forbidden from importing or installing heavy headless browser automation packages (Puppeteer, Playwright, Selenium).
   * The AI is strictly forbidden from creating test scripts or mock files anywhere outside `supporting files/testing/`.
   * The AI is strictly forbidden from executing `git commit`, `git merge`, `git rebase`, or `git push`. All Git actions must be executed manually by human hands.
