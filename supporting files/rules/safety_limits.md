# Safety Limits, Circuit Breakers & Abort Policies

## 1. Why Safety Limits Are Essential
Small web applications (like student projects, hobby blogs, and early startups) are fragile. If you hammer them with too much traffic when they are already struggling, you can permanently crash the server, corrupt database tables, or trigger expensive hosting bills.

Additionally, if your test sends high-speed traffic into an active security firewall (like Cloudflare or AWS WAF), the firewall will block your IP address, locking you out of your own website.

**Pusher's Safety Philosophy**: Be a helpful assistant, not a reckless battering ram. Pusher automatically detects when a server is in distress and hits the safety brakes before permanent damage happens.

---

## 2. The 3 Automatic Safety Brakes (Circuit Breakers)

Pusher constantly monitors incoming HTTP responses during every test. If danger is detected, it trips a circuit breaker and stops the test immediately.

```
                             [ Active Load Test Engine ]
                                         │
                    Evaluates Every Incoming Response & Heartbeat
                                         │
       ┌───────────────────┬─────────────┴─────┬───────────────────┐
       ▼                   ▼                   ▼                   ▼
 [ Brake 1: Crash ]  [ Brake 2: WAF ]    [ Brake 3: Lag ]    [ CPU Self-Check ]
 5 consecutive 5xx   HTTP 429 or WAF     p95 > 8,000ms       Pusher Event Loop
 errors in a row     Challenge Block     or 30% timeouts     Lag > 200ms x 5s
       │                   │                   │                   │
       └───────────────────┴─────────────┬─────┴───────────────────┘
                                         ▼
                            [ TRIP SAFETY BRAKES ]
                                         │
                     ├── 1. Cancel all active test tasks
                     ├── 2. Close all open network sockets
                     ├── 3. Mark Test Status as 'STOPPED_FOR_SAFETY'
                     └── 4. Show friendly plain-English advice
```

---

### Brake 1: Server Crash Breaker (5xx Errors) [Feature #11] (`crash_5xx_breaker.py`)
When a target application crashes, its server software (like Nginx, Apache, or Node.js) usually starts returning `500 Internal Server Error`, `502 Bad Gateway`, or `503 Service Unavailable`. Continuing to send requests into a crashed server makes recovery harder.

* **Dual Detection Logic**:
  1. **Consecutive Error Count**: **5 errors in a row** without any successful `2xx` response in between.
  2. **Rolling Window Error Ratio**: If more than **25%** of all responses return 5xx errors during any rolling 5-second window. (This catches alternating failures like `500, 200, 500, 200` where the consecutive counter resets but half the requests are failing).
* **Sample Size Protection**: To prevent a single error at the very start of a test from triggering a false shutdown, the rolling ratio breaker activates only after at least **20 total responses** have been received.
* **What Pusher does**:
  1. Stops sending new requests immediately.
  2. Closes all open network connections.
  3. Displays this simple advice:
     > *"Test stopped automatically: Your web server returned consecutive 500-level errors (it is likely crashing or running out of memory). Check your application console logs to see what crashed."*

---

### Brake 2: Firewall (WAF) & Rate-Limit Breaker [Feature #11] (`waf_429_breaker.py`)
Web Application Firewalls (like Cloudflare, AWS WAF, Sucuri, Akamai, or DataDome) and API rate limiters are designed to block abusive traffic. If Pusher hits an external firewall, continuing the test will get the tester's home or office IP address blacklisted.

* **Preventing False Alarms with the 2-in-1 Pusher Guard Middleware**:
  * Internal in-app rate limiters (like `slowapi` in Python or `express-rate-limit` in Node.js) might start returning `429 Too Many Requests` even though your server hardware is completely healthy.
  * When you install the **2-in-1 Pusher Guard Middleware** (`pusher_guard.py` or `pusherGuard.js`), Pusher sends the secret verification header `X-Pusher-Bypass: <KEY>` with every test request. Your server middleware recognizes this secret key and lets the load test pass through without triggering internal app-level rate limits.
  * If `429` or `403` errors still occur while the bypass header is active, Pusher knows an **external edge firewall** (like Cloudflare or AWS WAF) is blocking the requests, and Brake 2 safely engages!

* **When it trips**:
  * **HTTP 429 Too Many Requests**: 3 responses with status `429` inside 3 seconds (indicating an un-bypassed rate limiter or external edge limit).
  * **OR HTTP 403 with Firewall Signatures**:
    * Headers containing: `cf-ray`, `cf-chl-bypass`, `x-amzn-errortype`, `x-akamai-transformed`, or `x-datadome`.
    * Response body text mentioning: `"Cloudflare Ray ID"`, `"Attention Required!"`, `"AWS WAF"`, or `"Access Denied"`.
* **What Pusher does**:
  1. Instantly cancels all active test tasks.
  2. Emits this clear advice:
     > *"Test stopped: A Web Application Firewall (like Cloudflare or AWS WAF) or rate limiter blocked the test. Load testing against an active firewall hides your real server speed and risks getting your IP blocked. If this was caused by an in-app rate limiter, install the 2-in-1 Pusher Guard Middleware to allow test traffic through."*

#### Firewall Bypass Troubleshooting Box (`waf_429_breaker.py` & `english_advisor.py`)
When Pusher stops due to an HTTP 429 or 403 firewall block, follow these 3 clear remedies depending on your architecture:

┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      FIREWALL BYPASS TROUBLESHOOTING GUIDE                             │
├─────────────────────────┬──────────────────────────────────────────────────────────────┤
│ 1. In-App Rate Limiter  │ Install the 2-in-1 Pusher Guard middleware (pusher_guard.py  │
│    (FastAPI/Express)    │ or pusherGuard.js). Pusher will automatically inject the     │
│                         │ X-Pusher-Bypass secret key to allow test traffic through.    │
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ 2. Cloudflare Edge WAF  │ Add a 1-step Cloudflare WAF Custom Skip Rule:                │
│    (CDN / Edge Proxy)   │ If (http.request.headers["x-pusher-bypass"][0] == "SECRET")  │
│                         │ Action: Skip Rate Limiting & Managed Rules.                  │
├─────────────────────────┼──────────────────────────────────────────────────────────────┤
│ 3. Local Mock Testing   │ Switch to local development mode (PUSHER_MODE=local_dev).    │
│    (100% Firewall-Free) │ Run the mock target (mock_target_server.py) on port 8080 to  │
│                         │ test with zero cloud firewalls or risk of IP blacklisting.   │
└─────────────────────────┴──────────────────────────────────────────────────────────────┘

---

### Brake 3: Slowdown & Timeout Breaker [Feature #11] (`latency_8s_breaker.py`)
If the target website slows down so much that requests hang, the test engine will pile up pending tasks, giving false readings.

* **Strict Request Timeout**: Every single HTTP request has a hard timeout limit of **5.0 seconds** (user configurable between 2.0s and 10.0s).
* **When it trips**:
  * The **p95 response speed exceeds 8,000ms (8 seconds)** over a 10-second period.
  * **OR more than 30% of requests time out** (fail to respond within 5 seconds).
* **Sample Size Protection**: Requires a minimum of **20 completed requests** before evaluating latency breakers to prevent premature stops from initial cold-start delays.
* **What Pusher does**:
  * Stops the test and warns the developer that the target website is choking on requests.

---

## 3. Slower-PC Friendly CPU Self-Check [Feature #13] (`health_and_disconnect.py`)
Sometimes the laptop running Pusher gets busy (for example, if another program on your laptop starts using CPU). When that happens, Pusher's own code can lag, making it look like the target website is slow when it is actually your laptop that is slow!

To prevent false alarms on everyday budget laptops, Pusher uses a smart, gentle CPU monitor:

* **Gentle 500ms Heartbeat**: Pusher checks its internal event-loop delay once every **500ms** (instead of hammering the loop every 100ms), keeping CPU overhead under 1%.
* **1-Second Pre-Test Auto-Baseline**: Before sending any HTTP traffic, Pusher takes a 1-second auto-baseline measurement of the laptop's resting loop delay.
* **Warning Badge (150ms–200ms Lag)**: If lag drifts **150ms to 200ms** above baseline, Pusher displays a yellow advisory badge in the UI health bar (`SystemHealthBar.jsx`) without interrupting the test.
* **Pause VU Scaling (>200ms for 5s)**: If loop lag exceeds **200ms above baseline for 5 consecutive seconds** (5 heartbeat ticks in a row), Pusher temporarily pauses adding new virtual users. It maintains the current user count until the host CPU recovers, ensuring Pusher's own slowdown is never mistaken for a website bottleneck!

---

## 4. Intelligent CDN Cache Detector [Feature #12] (`cdn_cache_detector.py`)

Many modern hosting providers (like Vercel, Netlify, and Cloudflare) automatically cache web pages. When you load-test a cached page, you are testing Cloudflare's massive edge network, not your real server or database!

```
       [ Pusher Request ]
               │
               ▼
       [ CDN Edge Node (Cloudflare/Vercel) ] ──(Cache HIT: 5ms)──> [ Returns Saved Copy ]
               │
          (Cache MISS)
               ▼
     [ Your Real Server & Database ] (Where the real bottleneck lives!)
```

### How Pusher Detects Caching:
Pusher inspects headers on incoming responses for the tested endpoint:
* `cf-cache-status: HIT`
* `x-vercel-cache: HIT`
* `x-cache: HIT`
* `x-fastly-request-id`

### What Pusher shows:
If **more than 50% of responses are CDN Cache HITs**, Pusher keeps testing but shows a prominent yellow banner:
> *"⚠️ High Cache Hit Rate Detected (>50%): Your requests are being answered by a CDN edge cache (like Cloudflare or Vercel) in < 15ms. You are testing CDN bandwidth, not your real server or database. Turn on the 'Fresh Page Randomizer' in test settings to test your real backend!"*

---

## 5. Big Red "Emergency Stop" Button (Dual-Channel Safe) [Feature #8] (`EmergencyStopButton.jsx`)

Every load test interface must display a prominent, bright red **Emergency Stop** button.

```
┌────────────────────────────────────────────────────────────────────────┐
│  [■ EMERGENCY STOP]  (Click to halt test immediately in < 200ms)       │
└────────────────────────────────────────────────────────────────────────┘
```

* **Instant Action**: When clicked, Pusher cancels all asynchronous worker tasks and closes all open network connections in **less than 200 milliseconds**.
* **Dual-Channel Dispatch**: To prevent network lag from delaying the stop command, the frontend sends the stop signal over both the live WebSocket channel AND a direct HTTP POST request (`/api/v1/test/stop`).
* **Keeps Your Data**: It does NOT clear the screen. All charts, graphs, and statistics collected up to the exact millisecond you clicked Stop stay visible so you can review what happened.

---

## 6. Default Beginner Safety Limits

To keep beginners safe from accidental mistakes, Pusher enforces these limits:

| Setting | Beginner Default | Maximum Allowed Limit |
| :--- | :--- | :--- |
| **Virtual Users (VUs)** | `10 users` | `500 users` (Cloud) / `2,250 users` (Default Local 500MB Ceiling) / User-expandable up to 75% Host RAM |
| **Shared PaaS Subdomain Users**| `10 users` | `25 users` (Protects shared hosts) |
| **Test Duration** | `30 seconds` | `300 seconds (5 minutes)` |
| **Ramp-Up Time** | `5 seconds` (Linear) | Mandatory gradual start |
| **Max Requests / Sec (RPS)** | `50 RPS` | `2,500+ RPS` (Scales dynamically with VUs) |
| **Domain Ownership Check** | Mandatory | Must be verified before test starts (48h auto-expiry) |

> **Concurrency & Hardware Scaling Note**: Default concurrency is budgeted at **500 MB RAM for 2,250 VUs** using the deterministic model: $\text{RAM (MB)} = 50 + (\text{Active VUs} \times 0.20)$. Users with higher physical hardware RAM can manually scale concurrency up to **75% of total host RAM** (`floor(Host_RAM_MB × 0.75)`) and 70% OS File Descriptors.
