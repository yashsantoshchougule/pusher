# System Architecture & Development Standards

## 1. What is Pusher?
**Pusher** is an ultra-lightweight, beginner-friendly web load-testing tool. It is designed for students, solo developers, and creators of small web applications (like personal blogs, hackathon projects, and MVPs) to test how many users their app can handle before slowing down or crashing.

Unlike heavy enterprise tools, Pusher is built to run smoothly on everyday hardware with **₹0 spent** on cloud servers or paid services.

---

## 2. Project Hardware & The 2-Laptop Setup

Pusher is built by a 2-person development team using standard consumer hardware:
* **Developer Laptops**: Two standard laptops (16GB RAM, 512GB SSD each; one equipped with an NVIDIA RTX 4050).
* **Zero Dedicated GPU Required**: Load generation uses asynchronous network I/O and lightweight CPU tasks, meaning no expensive GPUs or server farms are needed.
* **Team Guidelines**: See [`team_collaboration.md`](file:///c:/yash/projects/pusher/supporting%20files/rules/team_collaboration.md) for full team division of labor, folder ownership, and API contract rules.

### The 2-Laptop Local Testing Setup
When testing a load generator, running both the load tester and the target app on the exact same laptop causes them to fight for the same CPU and RAM. To prevent false results, the team uses a 2-laptop setup connected over the same local Wi-Fi network:

```
┌──────────────────────────────────────┐         Local Wi-Fi Network         ┌──────────────────────────────────────┐
│               LAPTOP 1               │         (e.g., 192.168.1.x)         │               LAPTOP 2               │
│         [ The Load Tester ]          │ ──────────────────────────────────> │         [ The Target App ]           │
│                                      │   HTTP Load Traffic (Async I/O)     │                                      │
│ • Pusher Web UI (React + Tailwind)   │                                     │ • Mock Test Servers (Mocks Folder)   │
│ • FastAPI Backend (Python Async)     │ <────────────────────────────────── │ • Or Teammate's Real Web Application │
│ • Real-time Metrics & Charts         │        Live HTTP Responses          │ • Independent CPU & RAM Monitoring   │
└──────────────────────────────────────┘                                     └──────────────────────────────────────┘
```

* **Laptop 1 (Pusher Tester)**: Runs the React frontend dashboard and the FastAPI asynchronous load generation engine.
* **Laptop 2 (Target Server)**: Runs the mock test endpoints (`supporting files/testing/mocks/`) or the small web app being tested.
* **Benefit**: The load engine's CPU usage does not slow down the target website, giving realistic speed and capacity measurements for free.

#### Local Wi-Fi Connection & Firewall Rule:
* **Server Binding**: Laptop 2 must bind its mock server to `0.0.0.0` (all network interfaces) so Laptop 1 can reach it:
  ```python
  # Run mock server on Laptop 2
  uvicorn.run(app, host="0.0.0.0", port=8080)
  ```
* **Windows Firewall Note**: If Windows Defender Firewall blocks incoming traffic on Laptop 2, allow port `8080` in Windows Security settings or run this simple PowerShell command as Administrator on Laptop 2:
  ```powershell
  New-NetFirewallRule -DisplayName "Pusher Test Port 8080" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
  ```

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
                                          (External Domain or Laptop 2)
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

### Feature 13: Pusher CPU Self-Check & Client Disconnect Guard
* **CPU Self-Check**: Monitors Pusher's own event-loop lag. If the tester's laptop gets bogged down (`> 30ms` drift), it pauses adding virtual users so Pusher does not blame its own lag on the target website.
* **Client Disconnect Guard**: If the user closes their browser tab or Wi-Fi drops mid-test, the backend waits **15 seconds** for reconnection. If no client reconnects, it automatically halts the load test to prevent orphan tests from running in the background.

---

## 6. Project Directory Structure

All testing files, mock endpoints, and prototypes must be kept strictly inside `supporting files/testing/`:

```
pusher/
├── supporting files/
│   ├── rules/                       # Documentation and architecture rules
│   │   ├── architecture_and_standards.md   # Tech stack, features, and 2-laptop setup
│   │   ├── team_collaboration.md           # 2-person ownership, API contracts & Wi-Fi testing
│   │   ├── memory_management.md            # RAM limits, socket reuse, zero-buffering
│   │   ├── target_verification.md          # Free DNS/file verification & SSRF defense
│   │   ├── safety_limits.md                # 3 automatic safety brakes & emergency stop
│   │   └── github_workflow.md              # 2-person team Git roles & manual push rules
│   │
│   └── testing/                     # EXCLUSIVE home for all tests and prototypes
│       ├── README.md                # Testing instructions and checklist
│       ├── mocks/                   # Mock target servers for Laptop 2
│       ├── prototypes/              # Prototype async engine scripts
│       ├── benchmarks/              # RAM and speed benchmarking scripts
│       └── unit/                    # Unit tests for verification and SSRF blocking
│
├── frontend/                        # React + Vite + Tailwind UI
└── backend/                         # FastAPI + asyncio + aiohttp backend
```

> **STRICT RULE**: No test scripts, prototypes, or mock servers may be placed in the project root or source folders. They must stay strictly inside `supporting files/testing/`.

---

## 7. Simple Coding & Quality Standards
1. **Readable Code**: Write straightforward, well-commented Python and JavaScript. Avoid unnecessarily deep abstractions.
2. **Zero Memory Leaks**: Always close client sessions and sockets after every test run.
3. **No Heavy Dependencies**: Do not install headless browser packages (no Puppeteer, Playwright, or Selenium).
4. **Privacy First**: Never save user passwords, authorization tokens, or request payloads to disk or persistent databases.
