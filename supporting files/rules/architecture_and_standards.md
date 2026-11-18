# System Architecture & Development Standards

## 1. What is Pusher?
**Pusher** is an ultra-lightweight, beginner-friendly web load-testing tool. It is designed for students, solo developers, and creators of small web applications (like personal blogs, hackathon projects, and MVPs) to test how many users their app can handle before slowing down or crashing.

Unlike heavy enterprise tools, Pusher is built to run smoothly on everyday hardware with **₹0 spent** on cloud servers or paid services.

---

## 2. Consumer Hardware Efficiency & Local Mock Testing

Pusher is engineered to run with exceptional efficiency on everyday consumer hardware:
* **Hardware Requirements**: Runs smoothly on standard computers and laptops (16GB RAM, 512GB SSD recommended, though even 8GB RAM systems handle tests with ease).
* **Zero Dedicated GPU Required**: Load generation relies entirely on non-blocking asynchronous network I/O (`asyncio` and `aiohttp`) and lightweight event loops, meaning no GPUs, cloud compute clusters, or server farms are needed.
* **Team Guidelines**: See [`team_collaboration.md`](file:///c:/yash/projects/pusher/supporting%20files/rules/team_collaboration.md) for architectural subsystem guidelines and API contracts.

### Local Development & Mock Target Testing (`PUSHER_MODE=local_dev`)
When developing and testing Pusher itself, developers do not need a live public domain or paid cloud hosting. Pusher provides a dedicated local development mode:

```
┌───────────────────────────────────────┐         Local Loopback / Network        ┌───────────────────────────────────────┐
│         PUSHER LOAD RUNNER            │         (localhost / LAN IP)            │          MOCK TARGET SERVER           │
│                                       │ ──────────────────────────────────────> │                                       │
│ • Pusher Web UI (React + Tailwind)    │       HTTP Load Traffic (Async I/O)     │ • mock_target_server.py               │
│ • FastAPI Backend (Python Async)      │                                         │ • Listens on 0.0.0.0:8080             │
│ • RAM < 500MB (2,250 VUs, Scalable)   │ <────────────────────────────────────── │ • Returns 200 OK, 5xx, or 429 WAF     │
│ • PUSHER_MODE=local_dev               │          Live HTTP Responses            │ • Independent port or local host      │
└───────────────────────────────────────┘                                         └───────────────────────────────────────┘
```

* **Standalone Mock Target**: Developers run `supporting files/testing/mocks/mock_target_server.py`, which binds to `0.0.0.0:8080`.
* **Zero Fighting for Resources**: The mock server can be run on the same computer using a different port or on any other machine/VM across the local network.
* **No DNS or Cloud Costs**: In `PUSHER_MODE=local_dev`, domain ownership verification is bypassed for local IP addresses (`127.0.0.1`, `localhost`, and local subnet IPs), allowing instant zero-cost testing.

---

## 3. The 100% Free (₹0) Tech Stack

Every technology used in Pusher is 100% open-source and free forever:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        100% FREE (₹0) TECH STACK                       │
├───────────────────┬────────────────────────────────────────────────────┤
│ Frontend UI       │ React 18+ / Vite / Tailwind CSS / Chart.js         │
│ Backend API       │ Python 3.11+ / FastAPI / asyncio                   │
│ Socket Engine     │ aiohttp / httpx (Non-blocking async connections)   │
│ Live Streaming    │ WebSockets or Server-Sent Events (SSE)             │
│ Metrics Storage   │ Fixed-size in-memory buckets (HdrHistogram / Ring) │
│ Free Cloud Hosting│ Frontend on Vercel (Free), Backend on Render (Free)│
└───────────────────┴────────────────────────────────────────────────────┘
```

* **Frontend**: React + Vite + Tailwind CSS with lightweight live charts (Chart.js or Recharts). Deploys for free on Vercel or Netlify.
* **Backend**: Python 3.11+ with FastAPI and `asyncio`. Runs easily on a laptop or free cloud tiers (like Render or Railway free 512MB RAM tier).
* **HTTP Engine**: `aiohttp` or `httpx` using asynchronous sockets. It reuses persistent connections without spawning heavy browser instances.
* **Metrics**: In-memory rolling counters and fixed-size latency buckets (`< 5 MB` RAM total).
* **Strict 5-Color Hex Design System**:
  Pusher standardizes on a cohesive, modern developer visual theme across all dashboard views, modals, and telemetry graphs:
  - `#011425` (**Deep Midnight**): Deep canvas background, terminal/telemetry console backgrounds, and recessed tracks.
  - `#242424` (**Dark Charcoal**): Bento card surfaces, container backgrounds, navbar frames, and secondary panels.
  - `#5C7C89` (**Slate Blue-Gray**): Card borders, muted labels, secondary text, axis lines, and inactive badges.
  - `#1F4959` (**Ocean Teal**): Primary action buttons (CTA), active navigation pills, and live chart telemetry lines.
  - `#FFFFFF` (**Crisp White**): Primary headings, metric readouts, and high-contrast action text.

---

## 4. High-Level System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                     USER INTERFACE (Web Browser)                       │
│   • One-Click Safe Start (10 VUs, 30s duration, 5s linear ramp-up)     │
│   • Traffic Mode Selector (Step-by-Step, Sudden Rush, Steady Crowd)    │
│   • Simple API & Login Tester (GET / POST / PUT / DELETE)              │
│   • Fresh Page Randomizer Toggle (Bypasses caching)                    │
│   • Real-Time Live Speed & Error Dashboard                             │
│   • Big Red "Emergency Stop" Kill Switch (< 200ms abort)               │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ WebSockets / SSE Live Updates
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND & ORCHESTRATION                     │
│   • Single-Test Queue Lock (Only 1 test runs at a time in RAM)         │
│   • Mandatory Target Domain Verifier (DNS TXT & HTTP File Check)       │
│   • Hacker & Private IP Blocker (SSRF Protection & Safe DNS Pinning)   │
│   • Client Disconnect Guard (15s grace period auto-aborts if tab closed)│
│   • Generator Health Heartbeat (Monitors Pusher CPU lag)               │
│   • Safety Brakes Monitor (5xx Crashes, WAF Blocks, Latency Spikes)    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Async Non-blocking HTTP Requests
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    LOW-RESOURCE ASYNC LOAD ENGINE                      │
│   • Persistent TCP Connection Pool (Reuses sockets, Keep-Alive)        │
│   • Streaming Chunk Reader (Reads 4KB chunks, counts bytes, discards)  │
│   • In-Memory Latency Collector (Calculates p50, p90, p95, p99 speeds) │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    └───> Verified Target Website
                                          (External Domain or Local Mock Target)
```

---

## 5. Core Product Features (With Edge-Case Protection)

Pusher includes 13 built-in features focused on simplicity, safety, and operational reliability:

### Feature 1: One-Click Safe Start
Beginners do not need to guess complex configuration numbers. Clicking "Start Test" defaults to safe parameters: **10 virtual users**, a **30-second test duration**, and a mandatory **5-second gradual ramp-up**.
* **Beginner Guardrails**: New users cannot accidentally start a test with 10,000 users. Concurrency inputs are bounded with clear sliders from 1 to 500 VUs.

### Feature 2: Three Easy Traffic Modes
1. **Step-by-Step Capacity Finder (Step-Ramp)**:
   Slowly increases users in steps (e.g., 10 → 25 → 50 → 100 users, running each step for 15 seconds) to automatically find:
   * **Safe User Capacity**: Maximum users handled with fast response times and 0% errors.
   * **Breaking Point**: The exact user count where response times spike or errors start appearing.
2. **Sudden Rush (Users/Sec)**:
   Simulates a sudden wave of visitors (e.g., 20 new users arriving every second) to test how quickly the server scales up.
3. **Steady Crowd (Hold Load)**:
   Holds a constant number of users (e.g., 50 concurrent users) for up to 5 minutes (300 seconds maximum) to verify long-term stability and memory leaks.

```
   Speed /
 Latency
    │
    │                      [ Saturated / Breaking Zone ]
    │                     /
    │   Requests/Sec Flat ═════════════════════════════╗
    │                   /                              ║ (Website Crashes / 500 Errors)
    │                  /     Response Time Spikes ↗    ║
    │                 /     /                          ▼
    │                /     /
    │               /  *  <── [ KNEE OF THE CURVE: Safe Capacity Limit ]
    │              /  /
    │  Fast & Normal / Response Time Low
    │            /  /
    │           /  /
    └──────────┴──┴───────────────────────────────────────►
               0  10  25   50   100   150   200   250   (Virtual Users)
```

### Feature 3: Simple API & Login Tester
A collapsible, single-screen box supporting `GET`, `POST`, `PUT`, and `DELETE`.
* Allows sending custom HTTP headers (such as `Authorization: Bearer <token>`).
* Accepts small JSON request bodies (`< 4 KB`).
* **Privacy & Security Rule**: Authentication tokens, passwords, cookies, and sensitive payloads are **never logged or saved to disk**. They exist strictly in transient RAM during the active test.

### Feature 4: Fresh Page Randomizer (Cache Buster)
Many small websites use caching that returns the same saved page, hiding true server capacity. Pusher supports simple dynamic tags in URLs and request bodies:
* `{{random_int(min, max)}}`: Inserts a random number within a range (e.g., `/products?id={{random_int(1, 10000)}}`). Defaults to `1` through `1000000` if no range is specified.
* `{{uuid}}`: Inserts a freshly generated UUIDv4 string (e.g., `{"order_id": "{{uuid}}"}`).
* **Execution Rule**: Each virtual user replaces these tags dynamically on every single request iteration, forcing the target web server and database to do real work instead of returning cached data.

### Feature 5: Python Multi-Step Mode (Advanced Option)
Allows users to chain 2 to 3 lightweight HTTP requests in sequence for each virtual user without heavy browsers:
* *Step 1 (Login)*: Send `POST /login` with username and password.
* *Token Extraction*: The engine extracts the token from the JSON response (e.g., `response.json()["token"]` or `Set-Cookie` header) and saves it to a temporary variable `{{auth_token}}`.
* *Step 2 (Dashboard)*: Send `GET /dashboard` using `Authorization: Bearer {{auth_token}}`.
* *Step 3 (Profile)*: Send `GET /profile`.
* All steps run in lightweight async Python coroutines using the same socket pool.

### Feature 6: Simple English Advice
Instead of showing confusing raw errors, Pusher translates status codes and slowdowns into plain English:
* **HTTP 500 / 502**: *"Your backend code crashed or your web server lost contact with your app. Check your application console logs."*
* **HTTP 504**: *"Your database or backend took too long to answer. Try optimizing heavy queries or adding an index."*
* **HTTP 429**: *"Your app or firewall blocked the test because too many requests arrived at once."*
* **High Latency**: *"Your server is getting overwhelmed. Responses are taking longer than 2 seconds."*

### Feature 7: Live Speed Dashboard
Real-time graphs showing Requests Per Second (RPS), total request counts, error percentages, and latency percentiles (`p50`, `p90`, `p95`, `p99`).

### Feature 8: Big Red Emergency Stop Button
A prominent button visible on screen at all times during a test. Clicking it cancels all running tasks and closes network sockets in **under 200 milliseconds** while preserving all metrics on screen.

### Feature 9: Mandatory Domain Verification & 2-in-1 Pusher Guard
Prevents the tool from being used to attack unauthorized websites. Users must prove ownership before running a test:
* **Method A (Free DNS TXT Record)**: Add a TXT record `pusher-verify=<UUIDv4>` with 0 paid services needed.
* **Method B (Downloadable 2-in-1 Pusher Guard Middleware File)**: For dynamic backends (Python/FastAPI or Node.js/Express). A single dropped-in middleware file (`pusher_guard.py` or `pusherGuard.js`) that handles **both**:
  1. *Automatic Domain Verification*: Serves `GET /.well-known/pusher-challenge.txt`.
  2. *Automatic Backend Rate-Limiter Bypass*: Pusher automatically sends the secret `X-Pusher-Bypass: <KEY>` header during the load test. The middleware checks this header with constant-time comparison (`hmac.compare_digest`), allowing your in-app rate limiters (like SlowAPI or express-rate-limit) to let test traffic through while keeping edge firewalls vigilant.
* **Method C (Static Verification File)**: For static HTML / Jamstack / GitHub Pages sites, upload a static text file to `/.well-known/pusher-challenge.txt`.

### Feature 10: Hacker & Private Network Blocker (SSRF Defense)
Blocks requests to internal networks (`127.0.0.1`, `192.168.x.x`, `10.x.x.x`) and cloud metadata (`169.254.169.254`) in production mode.

### Feature 11: 3 Automatic Safety Circuit Breakers
Automatically halts tests if the target server returns 5 consecutive 5xx errors, triggers a WAF (HTTP 429), or slows down past 8 seconds.

### Feature 12: CDN Cache Detector
Alerts users if more than 50% of requests are answered by a CDN cache (like Cloudflare or Vercel edge) rather than the actual backend server.

### Feature 13: Slower-PC Friendly CPU Self-Check & Client Disconnect Guard
* **CPU Self-Check (`health_and_disconnect.py`)**:
  * Monitors Pusher's own event-loop lag with a lightweight **500ms heartbeat** (gentle on older dual-core or quad-core laptop CPUs).
  * Takes a **1-second pre-test auto-baseline** during idle startup so background processes don't trigger false warnings.
  * Shows a gentle warning banner if lag drifts **150ms–200ms** above baseline.
  * Pauses adding new virtual users only if lag exceeds **200ms above baseline for 5 consecutive seconds**, ensuring Pusher never blames its own laptop slowdown on the target website.
* **Client Disconnect Guard (`health_and_disconnect.py`)**: If the user closes their browser tab or Wi-Fi drops mid-test, the backend waits **15 seconds** for reconnection. If no client reconnects, it automatically halts the load test to prevent orphan tests from running in the background.

---

## 5. Option B: 6-Page Streamlined Post-Login UI Architecture

Pusher's frontend interface implements the **Option B Wireframe Design System**: a clean, 6-page navigation architecture that eliminates duplicated controls, keeps the main dashboard strictly as a read-only summary, and isolates setup controls into dedicated specialist views:

```
[ Top Header: PUSHER | RAM: 50MB / 500MB MAX (4KB Chunk Discard Active) | FD CAP: 70% | ••• Menu ]
┌─────────────────┬────────────────────────────────────────────────────────────────────────┐
│ [ NAVIGATION ]  │  ACTIVE VIEW DISPLAY AREA                                              │
├─────────────────┼────────────────────────────────────────────────────────────────────────┤
│ 1. Dashboard    │  Pure Read-Only 3-Box Summary:                                         │
│                 │  • Box 1: Target Status & Live 48h Countdown -> [ MANAGE TARGET -> ]   │
│                 │  • Box 2: Capacity Scorecard & Staged Profile -> [ EDIT TRAFFIC -> ]   │
│                 │  • Box 3: Live 1s Telemetry Stream Monitor -> [ VIEW TEST HISTORY -> ] │
│                 ├────────────────────────────────────────────────────────────────────────┤
│ 2. Verify Target│  Target Verification Wizard & Cloudflare WAF Mini-Screen Preview:      │
│                 │  • SSRF validation & IP loopback defense                               │
│                 │  • 1-Click "Download pusher_guard.py" (Sealed 48-Hour Lockbox)         │
│                 │  • Live 48-hour countdown timer & "Kill Active Guard ID" button        │
│                 ├────────────────────────────────────────────────────────────────────────┤
│ 3. Traffic Setup│  Traffic Profile & Safety Guardrails Configurator:                     │
│                 │  • 3 Modes: Step-Ramp, Sudden Rush, Steady Crowd with ASCII curve      │
│                 │  • RAM Budget & Hardware Ceiling: 250MB, 500MB (Default), 1GB, 2GB     │
│                 │  • Virtual Users slider + numeric input (dynamically capped by RAM)    │
│                 │  • Circuit breakers: 5xx threshold, 429 auto-abort, p95 ceiling       │
│                 ├────────────────────────────────────────────────────────────────────────┤
│ 4. API Builder  │  Multi-Step Sequential HTTP Request Chain Builder:                     │
│                 │  • Endpoint chaining (e.g., POST /auth/login -> GET /dashboard)        │
│                 ├────────────────────────────────────────────────────────────────────────┤
│ 5. Test History │  Searchable & Filterable Archive of Past Load Test Runs:               │
│                 │  • Search by Run ID / Target URL; filter by Mode and Verdict Status    │
│                 │  • 2-run checkbox selection for Before-vs-After benchmark comparison   │
│                 │  • 1-Click [ CLONE CONFIG ] to immediately stage past run parameters   │
│                 ├────────────────────────────────────────────────────────────────────────┤
│ 6. Reports      │  Analytical Capacity Reports & Comparative Breakdowns:                 │
│                 │  • Knee-of-the-Curve saturation point analysis                         │
│                 │  • Before-vs-After telemetry overlay for selected historical runs      │
└─────────────────┴────────────────────────────────────────────────────────────────────────┘
```

### The Option B Rule of Zero UI Duplication
- **Main Dashboard (`1. Dashboard`) is strictly read-only**: It displays the current operational state, live 1s telemetry stream, and staged configuration. It contains **zero** input boxes, sliders, mode radio buttons, or history logs.
- All forms, sliders, and configuration toggles are housed strictly in `2. Verify Target` and `3. Traffic Setup`. Navigation between views is initiated via clean directional triggers (`[ MANAGE TARGET IN VERIFY WIZARD → ]`, `[ EDIT TRAFFIC SETUP → ]`, `[ VIEW TEST HISTORY ARCHIVE (X) → ]`).

---

## 6. Scalable Core + Plugin Directory Blueprint

To keep Pusher clean, maintainable, and easy to extend flexibly, the codebase uses a **"Frozen Core vs. Scalable Plugins"** architecture.

### The "Frozen Core vs. Scalable Plugins" Design:
1. **`backend/core/` (Frozen Core)**:
   Contains the invariant, battle-tested engine infrastructure. These files enforce memory budgets, socket efficiency, safety guards, and typing contracts. Once written and tested, **`backend/core/` never needs editing when adding new features**.
2. **`backend/plugins/` (Scalable Plugins)**:
   Contains 5 modular folders for extensible functionality (`traffic_modes/`, `request_builders/`, `breakers_and_detectors/`, `verifiers/`, and `advisors_and_exporters/`). Each feature is a self-contained Python file with a `@register_*` decorator.
3. **`frontend/src/core_ui/` vs. `frontend/src/features/`**:
   Separates always-on foundation components (`EmergencyStopButton.jsx`, `SystemHealthBar.jsx`, network clients) from modular plug-and-play UI feature cards.

---

### The Complete Directory Tree (With Feature & Memory Rule Mappings)

```text
pusher/
├── backend/                                      # FastAPI + asyncio + aiohttp Backend
│   ├── main.py                                   # FastAPI startup, CORS & plugin auto-loader
│   ├── config.py                                 # [Feature #1, #10] Safe defaults & PUSHER_MODE
│   │
│   ├── core/                                     # FROZEN CORE (Engine, Security & Contracts)
│   │   ├── contracts.py                          # [API Contract] Shared REST & 1s WS JSON schemas
│   │   ├── plugin_registry.py                    # [Scalability] Auto-discovers files in plugins/
│   │   ├── orchestrator.py                       # [Feature #1, #8] Main test loop & <200ms abort
│   │   ├── socket_pool.py                        # [Memory Rule 3.1, 3.2] Keep-Alive & 60s DNS cache
│   │   ├── stream_reader.py                      # [Memory Rule 3.3, 3.4] 4KB discard, 10MB cap, 512B err
│   │   ├── queue_lock.py                         # [Memory Rule 3.5, 3.7] 1-test lock, 30s evict, 70% cap
│   │   ├── ssrf_and_dns.py                       # [Feature #10] IP/port blocker, PaaS cap & DNS pin
│   │   ├── health_and_disconnect.py              # [Feature #13] 500ms CPU check & 15s tab disconnect
│   │   └── metrics_store.py                      # [Feature #7 & Memory Rule 3.6] <5MB HdrHistogram ring
│   │
│   ├── plugins/                                  # SCALABLE EXTENSION SLOTS (Drop new files here)
│   │   ├── traffic_modes/                        # Slot 1: Virtual User Spawning Algorithms
│   │   │   ├── base_mode.py                      # [Feature #1] 10 VU / 30s / 5s ramp-up base rules
│   │   │   ├── step_ramp_finder.py               # [Feature #2] Mode 1: Step-by-Step Capacity Finder
│   │   │   ├── sudden_rush_mode.py               # [Feature #2] Mode 2: Sudden Rush (Users/Sec)
│   │   │   └── steady_crowd_mode.py              # [Feature #2] Mode 3: Steady Crowd (Hold Load)
│   │   │
│   │   ├── request_builders/                     # Slot 2: Headers, Randomizers & Multi-Step Chains
│   │   │   ├── api_login_builder.py              # [Feature #3] GET/POST/PUT/DELETE, RAM auth & <4KB JSON
│   │   │   ├── cache_randomizer.py               # [Feature #4] Dynamic {{random_int}} & {{uuid}} injector
│   │   │   └── multi_step_chain.py               # [Feature #5] Python 2-3 step chain & {{auth_token}}
│   │   │
│   │   ├── breakers_and_detectors/               # Slot 3: Real-Time Safety Brakes & Header Inspectors
│   │   │   ├── base_breaker.py                   # Blueprint class for 1-second response evaluators
│   │   │   ├── crash_5xx_breaker.py              # [Feature #11] Brake 1: 5 consecutive 5xx / >25% in 5s
│   │   │   ├── waf_429_breaker.py                # [Feature #11] Brake 2: HTTP 429 / 403 WAF detector
│   │   │   ├── latency_8s_breaker.py             # [Feature #11] Brake 3: p95 > 8,000ms / >30% timeouts
│   │   │   └── cdn_cache_detector.py             # [Feature #12] >50% CDN HIT header warning detector
│   │   │
│   │   ├── verifiers/                            # Slot 4: Target Ownership & Rate-Limit Bypass
│   │   │   ├── dns_txt_verifier.py               # [Feature #9] Method A: Cloudflare/Google DNS TXT check
│   │   │   └── guard_file_verifier.py            # [Feature #9] Method B: .well-known & pusher_guard file
│   │   │
│   │   └── advisors_and_exporters/               # Slot 5: Diagnostics & Future Report Exporters
│   │       ├── english_advisor.py                # [Feature #6] Plain-English error & WAF bypass advisor
│   │       └── pdf_health_card.py                # [Future Scope] 1-click PDF/MD capacity report exporter
│   │
│   └── api/                                      # FastAPI REST & WebSocket Endpoints
│       ├── routes_verify.py                      # [Feature #9] POST /verify/dns, /http & /middleware
│       ├── routes_test.py                        # [Feature #1, #8] POST /test/start, /stop, GET /status
│       └── ws_telemetry.py                       # [Feature #7, #8, #13] 1s JSON stream & WS instant stop
│
├── frontend/                                     # React 18 + Vite + Tailwind UI
│   └── src/
│       ├── App.jsx                               # Single-screen dashboard layout coordinator
│       ├── core_ui/                              # Always-on global controls & network services
│       │   ├── EmergencyStopButton.jsx           # [Feature #8] Big Red <200ms dual-channel (WS+HTTP) stop
│       │   ├── SystemHealthBar.jsx               # [Feature #13] Displays queue state & CPU lag notices
│       │   ├── apiClient.js                      # [API Contract] REST client for verify, start & HTTP stop
│       │   └── telemetrySocket.js                # [Feature #7, #13] 1s WS listener & 15s reconnect guard
│       │
│       └── features/                             # Modular UI Feature Cards (1 folder per feature group)
│           ├── verification_wizard/
│           │   └── VerificationWizard.jsx        # [Feature #9] DNS guide & 1-click pusher_guard download
│           ├── traffic_config/
│           │   └── TrafficConfigPanel.jsx        # [Feature #1, #2, #4] Safe Start, 3 modes & randomizer
│           ├── api_tester_drawer/
│           │   └── ApiRequestDrawer.jsx          # [Feature #3, #4, #5] API methods, headers & multi-step
│           ├── live_dashboard/
│           │   └── LiveTelemetryCharts.jsx       # [Feature #7] Live RPS, status counts & p50-p99 graphs
│           ├── diagnostics_advisor/
│           │   └── DiagnosticsBanner.jsx         # [Feature #6, #11, #12] English advice, WAF & CDN alerts
│           └── baseline_compare/                 # [Future Scope] Drop new UI feature cards here later
│
└── supporting files/
    ├── rules/                                    # Architecture, memory, safety, verify & workflow rules
    ├── plans/                                    # Technical design & architecture plans
    └── testing/                                  # EXCLUSIVE repository for all test scripts & mocks
        ├── mocks/
        │   └── mock_target_server.py             # [Local Dev Setup] Mock target server (0.0.0.0:8080)
        ├── prototypes/
        │   └── engine_prototype.py               # Standalone async socket & plugin experiments
        ├── benchmarks/
        │   └── memory_benchmark.py               # [Memory Rule 2] Verifies <500MB RAM at 2,250 VUs (Scalable to 75% Host RAM)
        └── unit/
            └── test_ssrf_and_plugins.py          # [Feature #9, #10, #11] Tests SSRF, verify & breakers
```

> **STRICT RULE**: No test scripts, prototypes, or mock servers may be placed in the project root or source folders. They must stay strictly inside `supporting files/testing/`.

---

### How to Add Future Features in 1 File (Zero Core Edits)

With this architecture, adding a new feature never touches `backend/core/`. You simply create one new file in the appropriate `backend/plugins/` folder and register it with a decorator:

```python
# backend/plugins/traffic_modes/spike_test.py
from core.plugin_registry import register_traffic_mode

@register_traffic_mode(
    name="spike_test",
    display_title="Sudden Traffic Spike",
    description="Surges load from 10 to 500 VUs in 2 seconds to test auto-scaling."
)
class SpikeTestMode:
    async def generate_schedule(self, target_vus: int, duration_sec: int):
        # Your custom spike calculation here
        pass
```

On startup, `backend/core/plugin_registry.py` automatically discovers this file, registers it, and `GET /api/v1/plugins` automatically sends it to the React UI. The frontend dynamically renders the new mode in the traffic selector dropdown without any hardcoded changes!

---

## 7. Simple Coding & Quality Standards
1. **Readable Code**: Write straightforward, well-commented Python and JavaScript. Avoid unnecessarily deep abstractions.
2. **Zero Memory Leaks**: Always close client sessions and sockets after every test run.
3. **No Heavy Dependencies**: Do not install headless browser packages (no Puppeteer, Playwright, or Selenium).
4. **Privacy First**: Never save user passwords, authorization tokens, or request payloads to disk or persistent databases.
