# Team Collaboration & 2-Person Development Rules

## 1. Overview & Team Mission
This document defines how our 2-person development team works together on **Pusher**. 

Building a high-performance load tester as a 2-person team requires clear boundaries. Without strict rules, teammates accidentally edit the same files, cause stressful Git merge conflicts, break frontend-backend connections, or get misleading load-test numbers by running everything on a single laptop.

Following these 6 rules ensures zero merge conflicts, reliable code, and smooth teamwork with **₹0 spent** on paid tools or cloud servers.

---

## 2. Master ASCII Diagram: Team Workflow & Wi-Fi Testing

```
========================================================================================
PART 1: GIT COLLABORATION (SEPARATE BRANCHES -> PULL REQUEST -> MAIN)
========================================================================================

    PARTNER 1 (Laptop 1)                              PARTNER 2 (Laptop 2)
  [ branch: backend-dev ]                            [ branch: frontend-dev ]
  • Owns: backend/core/                              • Owns: frontend/src/core_ui/
  • Owns: backend/plugins/                           • Owns: frontend/src/features/
  • Owns: backend/api/                               • Owns: testing/mocks/ (Laptop 2)
  • Owns: testing/prototypes/                        • Owns: UI Dashboard & Live Charts
  • Owns: testing/benchmarks/ & unit/                • Owns: Verification Wizard Modal
            │                                                  │
            │ Manual commit & push                             │ Manual commit & push
            ▼                                                  ▼
   origin/backend-dev                                 origin/frontend-dev
            │                                                  │
            └───────────────► GitHub Pull Request ◄────────────┘
                              (Peer Review & Approval)
                                         │
                                         ▼
                                   [ main Branch ]
                         (Always working, tested code)

========================================================================================
PART 2: LIVE WI-FI LOAD TESTING (LAPTOP 1 TESTS LAPTOP 2 OVER LOCAL WI-FI)
========================================================================================

┌───────────────────────────────────────┐         Local Wi-Fi Network         ┌───────────────────────────────────────┐
│               LAPTOP 1                │         (e.g., 192.168.1.x)         │               LAPTOP 2                │
│       [ The Load Test Runner ]        │ ──────────────────────────────────> │         [ The Target Server ]         │
│                                       │   HTTP Load Traffic (Async I/O)     │                                       │
│ • Runs Pusher Backend & Web UI        │                                     │ • Runs Mock Target Servers (Mocks)    │
│ • RTX 4050 / 16GB RAM / 512GB SSD     │                                     │ • 16GB RAM / 512GB SSD Laptop         │
│ • RAM kept < 250MB for 1,000 VUs      │ <────────────────────────────────── │ • Listens on 0.0.0.0:8080             │
│ • PUSHER_MODE=local_dev               │        Live HTTP Responses          │ • Unaffected by Pusher CPU load       │
└───────────────────────────────────────┘                                     └───────────────────────────────────────┘
```

---

## 3. The 6 Core Team Collaboration Rules

### Rule 1: Strict Role & Folder Ownership (Zero Merge Conflict Rule)
To make Git merge conflicts virtually impossible, our repository is divided into strict physical territories:

| Partner | Role | Folders Exclusively Owned | Allowed Responsibilities |
| :--- | :--- | :--- | :--- |
| **Partner 1** | Backend, Security & Engine | • `backend/core/`<br>• `backend/plugins/`<br>• `backend/api/`<br>• `supporting files/testing/prototypes/`<br>• `supporting files/testing/benchmarks/`<br>• `supporting files/testing/unit/` | • Engine core (`socket_pool.py`, `stream_reader.py`, `orchestrator.py`)<br>• Scalable plugins (`traffic_modes/`, `breakers_and_detectors/`, `verifiers/`)<br>• Domain ownership verifier & safe DNS pinning<br>• 2-in-1 Pusher Guard generator & `X-Pusher-Bypass` header injection<br>• Safety circuit breakers & CPU lag monitor |
| **Partner 2** | Frontend UI & Mock Targets | • `frontend/src/core_ui/`<br>• `frontend/src/features/`<br>• `supporting files/testing/mocks/` | • React + Tailwind CSS dashboard (`core_ui/` & `features/`)<br>• Live speed & latency charts (`live_dashboard/`)<br>• Big Red `<200ms` Emergency Stop button (`core_ui/EmergencyStopButton.jsx`)<br>• Verification wizard UI with "Download 2-in-1 Pusher Guard" modal<br>• Standalone mock target servers for Laptop 2 (`server_200_ok.py`, etc.) |

#### Shared Files Rule:
* Neither partner may edit files in the other partner's directory without discussing it first.
* All test scripts, mock endpoints, and benchmarks must stay strictly inside `supporting files/testing/`. No test scripts are allowed in project root or source folders.

---

### Rule 2: The "API Contract First" Rule (Connecting Frontend & Backend)
Before Partner 1 writes backend code or Partner 2 builds UI components, both partners must agree on the exact data format exchanged between `frontend/` and `backend/`.

> **FROZEN CORE CONTRACTS**: All REST request/response bodies and WebSocket telemetry frames are formally defined and locked inside **`backend/core/contracts.py`** using Pydantic models. Any change to a key name or field type must be coordinated between both partners before `contracts.py` is modified.

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

> **IMPORTANT**: If Partner 1 needs to rename or change a JSON key, they must notify Partner 2 **before** committing the change so the frontend charts do not break!

---

### Rule 3: 2-Person Manual Git & Branching Workflow
To guarantee human control and clean code history:
* **The AI assistant is 100% forbidden from executing `git commit`, `git merge`, `git rebase`, or `git push`.** All Git commands are typed manually by the human partners.

```
       [ main Branch ] (Protected: Only tested, working code)
              ▲
              │ Pull Request (Review & Merge)
       ┌──────┴──────┐
       │             │
  backend-dev   frontend-dev
  (Partner 1)   (Partner 2)
```

#### Daily Step-by-Step Sync Protocol:
1. **Start of Work (Sync with Main)**:
   ```bash
   # On your laptop:
   git checkout backend-dev   # (or frontend-dev for Partner 2)
   git pull origin main
   ```
2. **Inspect Changes**:
   ```bash
   git status
   git diff
   ```
3. **Stage Only Your Owned Folder**:
   ```bash
   # Partner 1 (Backend, Plugins, Tests):
   git add backend/ "supporting files/testing/prototypes/" "supporting files/testing/benchmarks/" "supporting files/testing/unit/"
   
   # Partner 2 (Frontend UI, Mocks):
   git add frontend/ "supporting files/testing/mocks/"
   ```
4. **Manual Descriptive Commit**:
   ```bash
   git commit -m "feat(backend): add consecutive 5xx error counter to circuit breaker"
   ```
5. **Push to Your Branch**:
   ```bash
   git push origin backend-dev   # (or frontend-dev)
   ```
6. **Merging to Main via Pull Request**:
   * Open a Pull Request (PR) on GitHub from your branch to `main`.
   * The other partner reviews the PR and approves it.
   * Merge cleanly into `main`.

---

### Rule 4: Two-Laptop Hardware & Wi-Fi Testing Protocol
Our team uses two standard laptops:
* **Hardware Specs**: Both laptops have 16GB RAM and 512GB SSD (one laptop features an NVIDIA RTX 4050 GPU, which is left free for other tasks since Pusher uses lightweight async CPU/network I/O).

#### The Wi-Fi Test Setup:
Running the load generator and the target server on the same laptop causes CPU contention and produces distorted latency numbers. We solve this by splitting duties across laptops over local Wi-Fi:

1. **Connect to Same Network**: Both laptops connect to the same home Wi-Fi network or a phone mobile hotspot.
2. **Laptop 2 (Target Server)**:
   * Finds its local IP address (e.g., `ipconfig` on Windows shows `192.168.1.50`).
   * Starts the mock target server from `supporting files/testing/mocks/`:
     ```bash
     python supporting\ files/testing/mocks/mock_target_server.py
     ```
   * Listens on `0.0.0.0:8080`.
3. **Laptop 1 (Pusher Tester)**:
   * Sets `PUSHER_MODE=local_dev` in its `.env` file.
   * Starts the FastAPI backend and React frontend.
   * Enters the target URL: `http://192.168.1.50:8080`.
   * Clicks **Start Test**.
4. **Result**: Realistic network testing with zero cloud server costs, zero DNS delays, and independent CPU monitoring.

---

### Rule 5: Shared Environment & Setup Rules
To prevent the classic "it works on my laptop but crashes on yours" dilemma:
1. **Identical Runtime Versions**:
   * **Python**: Python 3.11+ on both laptops.
   * **Node.js**: Node 18+ LTS on both laptops.
2. **Locking Dependencies Immediately**:
   * Whenever Partner 1 installs a new Python library, they must immediately update `backend/requirements.txt`:
     ```bash
     pip freeze > backend/requirements.txt
     ```
   * Whenever Partner 2 installs a new npm package, they must ensure it is saved in `frontend/package.json`:
     ```bash
     npm install <package> --save
     ```
3. **Environment Security**:
   * Never commit `.env`, `.env.local`, `node_modules/`, `venv/`, or log files to Git.
   * Keep a clear, sanitized template file named `.env.example` in the project root so both teammates know what variables are required.

---

### Rule 6: AI Assistant Rules for Both Teammates
Both teammates use AI coding tools on their laptops. To ensure both AI instances follow the exact same architecture:
1. **Context Loading**: Before asking an AI assistant to write or modify code on either laptop, the developer must instruct the AI to read all Markdown files in `supporting files/rules/`.
2. **Strict Prohibitions for AI**:
   * The AI is strictly forbidden from importing or installing heavy headless browser automation packages (Puppeteer, Playwright, Selenium).
   * The AI is strictly forbidden from creating test scripts or mock files anywhere outside `supporting files/testing/`.
   * The AI is strictly forbidden from running `git commit`, `git merge`, `git rebase`, or `git push`. All Git actions must be executed manually by human hands.
