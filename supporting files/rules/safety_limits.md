# Safety Limits, Circuit Breakers & Abort Policies

## 1. Why Safety Limits Are Essential
Small web applications (like student projects, hobby blogs, and early startups) are fragile. If you hammer them with too much traffic when they are already struggling, you can permanently crash the server, corrupt database tables, or trigger expensive hosting bills.

Additionally, if your test sends high-speed traffic into an active security firewall (like Cloudflare or AWS WAF), the firewall will block your IP address, locking you out of your own website.

**Pusher's Safety Philosophy**: Be a helpful assistant, not a reckless battering ram. Pusher automatically detects when a server is in distress and hits the safety brakes before permanent damage happens.

---

## 2. The 3 Automatic Safety Brakes (Circuit Breakers)

Pusher monitors incoming HTTP responses during each run. When a breaker trips, the engine cancels and drains the active work. The diagram includes the planned CPU self-check described in section 3.

```
                             [ Active Load Test Engine ]
                                         │
                    Evaluates Every Incoming Response & Heartbeat
                                         │
       ┌───────────────────┬─────────────┴─────┬───────────────────┐
       ▼                   ▼                   ▼                   ▼
 [ Brake 1: Crash ]  [ Brake 2: WAF ]    [ Brake 3: Lag ]    [ CPU Self-Check ]
 5 consecutive 5xx   3 HTTP 429 in 3s    p95 over ceiling   Pusher Event Loop
 errors in a row     or marked 403       or >30% timeouts   Lag > 200ms x 5s
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

* **When it trips**:
  * **HTTP 429 Too Many Requests**: 3 responses with status `429` inside 3 seconds (indicating an application or edge rate limit).
  * **OR HTTP 403 with Firewall Signatures**:
    * Headers containing: `cf-ray`, `cf-chl-bypass`, `x-amzn-errortype`, `x-akamai-transformed`, or `x-datadome`.
    * Response body text mentioning: `"Cloudflare Ray ID"`, `"Attention Required!"`, `"AWS WAF"`, or `"Access Denied"`.
* **What Pusher does**:
  1. Instantly cancels all active test tasks.
  2. Prompts the operator to review application and edge logs for the block. The Guard verifies ownership only. Use local sandbox mode for offline checks or approved staging with ordinary test credentials for capacity tests.

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

Status: planned design. The current engine does not pause scaling based on event-loop lag.
Sometimes the laptop running Pusher gets busy (for example, if another program on your laptop starts using CPU). When that happens, Pusher's own code can lag, making it look like the target website is slow when it is actually your laptop that is slow!

To prevent false alarms on everyday budget laptops, Pusher uses a smart, gentle CPU monitor:

* **Gentle 500ms Heartbeat**: Pusher checks its internal event-loop delay once every **500ms** (instead of hammering the loop every 100ms), keeping CPU overhead under 1%.
* **1-Second Pre-Test Auto-Baseline**: Before sending any HTTP traffic, Pusher takes a 1-second auto-baseline measurement of the laptop's resting loop delay.
* **Warning Badge (150ms–200ms Lag)**: If lag drifts **150ms to 200ms** above baseline, Pusher displays a yellow advisory badge in the UI health bar (`SystemHealthBar.jsx`) without interrupting the test.
* **Pause VU Scaling (>200ms for 5s)**: If loop lag exceeds **200ms above baseline for 5 consecutive seconds** (5 heartbeat ticks in a row), Pusher temporarily pauses adding new virtual users. It maintains the current user count until the host CPU recovers, ensuring Pusher's own slowdown is never mistaken for a website bottleneck!

---

## 4. Intelligent CDN Cache Detector [Feature #12] (`cdn_cache_detector.py`)

Status: planned design. The current edge diagnostics report an observed response and the engine enforces its firewall breaker.

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

## 5. Emergency Stop

The dashboard sends an authenticated HTTP POST to `/api/load/stop` with the active run ID. The same control works after HTTP status recovery when WebSockets are down. The engine cancels and drains workers, closes the run's client, and saves the report. Measure elapsed stop time in the intended environment.

---

## 6. Traffic profile defaults and admission limits

The following values apply to the dashboard traffic profile. Direct API callers may supply different settings within the backend limits.

| Setting | Profile default | Enforced rule |
| :--- | :--- | :--- |
| **Virtual users** | 100 | Uses the RAM budget and the worker limit exposed by the backend |
| **Duration** | 30 seconds | Up to 24 hours, with the remaining Guard lifetime enforced |
| **Traffic shape** | Step ramp | The selected mode determines when active users are added |
| **Domain ownership** | Required for live targets | Uses a Guard for the verified origin that expires after 48 hours |

The 500 MB budget models 2,250 VUs according to $\text{RAM (MB)} = 50 + (\text{Active VUs} \times 0.20)$. The backend also bounds the RAM budget at 75% of host RAM and applies the OS worker limit. These limits are inputs to admission. Measure throughput and actual RAM use on the intended host.
