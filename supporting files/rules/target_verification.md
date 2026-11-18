# Target Verification & Abuse Prevention Rules

## 1. Why Domain Verification is Mandatory
Load-testing tools generate hundreds or thousands of web requests per minute. If anyone could type in any website address and hit "Start", malicious actors could use Pusher as an attack weapon to perform a **Distributed Denial of Service (DDoS)** attack against schools, governments, or competing businesses.

**Pusher's Core Security Law**: You can only test a website if you can prove that you own it or have administrative control over it. Pusher will never fire a single load-testing request at an unverified website.

---

## 1.1 Three-Stage Live URL Syntax, Async DNS & HTTP Reachability Auto-Check
To prevent users from deploying guards or running load tests against non-existent, offline, or mistyped domains, Pusher performs an automatic, debounced (600ms) 3-stage validation (`POST /api/target/validate-url`):

1. **Stage 1 — Syntax & SSRF Boundary Guard**:
   - Enforces `http://` or `https://` scheme and valid domain syntax (contains dot in hostname).
   - Rejects loopbacks (`localhost`, `127.0.0.1`), private networks (`10.x`, `172.16.x`, `192.168.x`), and link-local cloud metadata (`169.254.169.254`) with status `SSRF_BLOCKED`.
2. **Stage 2 — Real-Time Async DNS Resolution**:
   - Resolves hostname via async DNS with 3.0s timeout.
   - If the domain does not exist in DNS (`socket.gaierror`), computes close typo matches against common hosting and developer domains (`github.com`, `gitlab.com`, `vercel.app`, `netlify.app`, `railway.app`, etc.) using `difflib.get_close_matches(hostname, COMMON_DOMAINS, n=2, cutoff=0.6)`.
   - Returns status `DNS_NOT_FOUND` and clickable suggestion chips.
3. **Stage 3 — Live HTTP/HTTPS Reachability Probe**:
   - Probes target server with lightweight `HEAD` (falling back to `GET` on HTTP 405) with 4.0s timeout.
   - If server responds with HTTP `< 500`: returns `REACHABLE` (`URL VERIFIED & LIVE`).
   - If connection times out or is refused: returns `UNREACHABLE` with smart typo suggestions.
4. **Guard Generation Lockdown**:
   - `POST /api/target/generate-guard` verifies URL reachability and rejects non-existent/unreachable domains with `HTTP 422 Unprocessable Entity`.
   - In UI, `DOWNLOAD PUSHER_GUARD.PY` is disabled until target is verified reachable (or Sandbox mode is active).

---

## 2. The Verification Methods

Pusher offers multiple 100% free ways to verify domain ownership and safely bypass in-code rate limiters:

```
               [ User Enters Target Website: https://app.example.com ]
                                        │
                         Selects Verification Method
                                        │
      ┌─────────────────────────────────┼─────────────────────────────────┐
      ▼                                 ▼                                 ▼
[ Method A: DNS TXT ]      [ Method B: 2-in-1 Guard ]        [ Method C: Static .txt ]
Add TXT record at:         Download pusher_guard.py          Upload static text file
_pusher-challenge.domain   Runs on your backend:             to .well-known/ folder
Value: pusher-verify=...   1. Auto-serves verify route       (For static Jamstack /
(Best for apex domains)    2. Auto-bypasses rate limit       GitHub Pages sites)
      │                                 │                                 │
      └─────────────────────────────────┼─────────────────────────────────┘
                                        ▼
                     [ Pusher Verification Engine Validates ]
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                               ▼
                 [ Valid Match ]               [ Failed / Missing ]
                        │                               │
                Unlock Load Testing              Reject with Error
```

---

### Method A: DNS TXT Challenge [Feature #9] (`dns_txt_verifier.py`)
1. **Pusher Generates a Unique Code**:
   Pusher creates a safe, cryptographically signed token:
   `pusher-verify=<UUIDv4>-<HMAC>`
2. **User Adds a DNS Record**:
   The user logs into their domain registrar (Namecheap, GoDaddy, Cloudflare, etc.) and creates a `TXT` record:
   * **Host / Name**: `_pusher-challenge`
   * **Value**: `pusher-verify=<UUIDv4>-<HMAC>`
3. **Pusher Checks Public DNS**:
   Pusher queries free public DNS resolvers (**Cloudflare 1.1.1.1** and **Google 8.8.8.8**) at ₹0 cost.
   * **Student Friendly**: Students who do not own a paid domain can test this 100% for free using **DuckDNS** (free dynamic DNS) or a free domain from the **GitHub Student Developer Pack**.
4. **DNS Propagation Retry**:
   DNS records sometimes take 30 to 60 seconds to spread across the internet. If verification fails on the first try, Pusher provides an automatic retry button that checks again 3 times, spaced 5 seconds apart.
5. **Verification Complete**: If the TXT record matches, Pusher marks the domain as `VERIFIED`.

---

### Method B: The "2-in-1 Pusher Guard Middleware File" [Feature #9] (`guard_file_verifier.py`)
When testing a dynamic web application (built with FastAPI, Flask, Express, Django, etc.), developers face a common frustration: **their own in-app rate limiters** block the load test after 50 to 100 requests with `HTTP 429 Too Many Requests`, and API routes require authenticated sessions.

To solve this, Pusher provides a downloadable **Cryptographically Signed & Sealed Server Middleware File** (`pusher_guard.py` for Python or `pusherGuard.js` for Node.js).

#### The Architecture of the Sealed Guard File:
1. **Job 1 (Automatic Domain Verification & Handshake)**:
   The middleware automatically registers the `GET /__pusher_verify?nonce=...` route on your web server, validates the 48-hour expiration window, computes the HMAC challenge response, and returns `status="ACTIVE"`, `proof`, `file_sha256`, and `auth_bypass_ready=True`.
2. **Job 2 (Cryptographically Signed Backend Rate-Limiter & Auth Bypass)**:
   During active load tests and dry-runs, Pusher automatically signs every outgoing request:
   - `X-Pusher-Guard-ID: {guard_id}`
   - `X-Pusher-Timestamp: {current_unix_minute}`
   - `X-Pusher-Signature: {hmac_sha256(secret, f"{guard_id}:{current_unix_minute}")}`
   - `X-Pusher-Bypass: {guard_id}-SIGNED`
   The middleware checks the signature using constant-time comparison (`hmac.compare_digest`) with a `±1` minute clock-skew window. When verified:
   - **App-Level Rate Limiter Bypass**: Sets `request.state.pusher_bypass = True` and rotates synthetic client IP in `request.scope["client"]` per request so IP-based rate limiters (`slowapi`, Starlette throttles) never block Pusher VUs with `HTTP 429`.
   - **App-Level Auth Bypass**: Injects synthetic `Authorization: Bearer pusher_bypass_{guard_id}` and sets `request.scope["user"] = {"id": "pusher_load_test_vu", "role": "load_tester", "bypass_auth": True}` if no custom auth header was supplied.
   - **Normal Traffic Security**: Unsigned requests pass through untouched without any bypass.
3. **Job 3 (Byte-Level Self-Lock Integrity Check)**:
   `pusher_guard.py` verifies its own SHA-256 seal on load. Modifying even 1 byte raises:
   `RuntimeError("PUSHER GUARD LOCKED: Unauthorized modification to pusher_guard.py detected.")`.

#### Enforced Security, Device Lock & Quota Invariants:
- **Device-Bound Hardware Lock (`DEV-XXXXXXXXXXXX`)**: Generating `pusher_guard.py` captures the creator's device hardware fingerprint (`localStorage` seed + platform + screen + timeZone + concurrency) into `creator_device_hash` and embeds it inside the sealed vault.
- **Host-Machine Lock**: Inside `pusher_guard.py`, `_get_host_fingerprint()` binds to `uuid.getnode() + platform.node()` on first handshake. Copying the file to another server triggers an immediate mismatch tripwire.
- **Persistent SQLite Tombstone Registry (`burned_guards`)**: All burned Guard IDs are written to table `burned_guards` in `backend/pusher_runs.db` (`guard_id`, `burn_reason`, `creator_device_hash`, `offending_device_hash`, `burned_at`). Once written, the ID can never be used, re-issued, or verified again.
- **3 Irreversible Kill & Permanent Burn Triggers**:
  1. **Trigger 1 — Cross-Device Usage Violation (`DEVICE_MISMATCH_VIOLATION`)**: If any request (`verify`, `load/start`, `kill`) arrives from a device other than the creator device, or if the host machine fingerprint changes, the Guard ID is permanently killed, the 48h timer is halted at `00:00:00`, active load tests are aborted, and `HTTP 403 Forbidden` is returned.
  2. **Trigger 2 — Automatic 48-Hour Expiry Kill (`EXPIRED_48H`)**: Once `time.time() >= expires_at`, the ID is automatically permanently killed across all endpoints.
  3. **Trigger 3 — Manual User Revocation (`MANUAL_USER_KILL`)**: Creator clicks `KILL ID`, burning the active token into SQLite and unlocking `DOWNLOAD PUSHER_GUARD.PY` (subject to 3/day quota).
- **Kill-First Rule (`HTTP 409 Conflict`)**: Generating a second `pusher_guard.py` while an active unrevoked guard exists is blocked until the active ID is killed via `POST /api/target/kill`.
- **3/Day Rate Limit (`HTTP 429 Too Many Requests`)**: Maximum 3 guard generations per rolling 24-hour window.

#### Copy-Ready Example: `pusher_guard.py` (FastAPI / Python)
The user clicks **"Download pusher_guard.py"** in Pusher's UI and drops it into their backend project:

```python
# pusher_guard.py (Generated by Pusher for your backend)
import hmac
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

PUSHER_VERIFY_TOKEN = "pusher-verify=8f9d2a1b-4c3e-4f5a-9b8c-7d6e5f4a3b2c"
PUSHER_BYPASS_SECRET = "psh_secret_99a8b7c6d5e4f3a2b1c0"

def setup_pusher_guard(app: FastAPI):
    # Job 1: Serves domain ownership verification route
    @app.get("/.well-known/pusher-challenge.txt", response_class=PlainTextResponse)
    @app.get("/.well-known/pusher-verify", response_class=PlainTextResponse)
    async def verify_domain():
        return PUSHER_VERIFY_TOKEN

    # Job 2: Bypasses backend rate limiter for verified Pusher tests
    @app.middleware("http")
    async def pusher_bypass_middleware(request: Request, call_next):
        incoming_key = request.headers.get("X-Pusher-Bypass", "")
        # Constant-time comparison stops timing attacks
        if hmac.compare_digest(incoming_key, PUSHER_BYPASS_SECRET):
            request.state.is_pusher_test = True
        else:
            request.state.is_pusher_test = False
        return await call_next(request)
```

**How the Developer Uses It in `main.py`**:
```python
from fastapi import FastAPI
from pusher_guard import setup_pusher_guard

app = FastAPI()
setup_pusher_guard(app)  # That's it! Verification and bypass are active.
```

#### Node.js / Express Equivalent: `pusherGuard.js`
```javascript
// pusherGuard.js (Generated by Pusher for Node/Express)
const crypto = require('crypto');

const PUSHER_VERIFY_TOKEN = "pusher-verify=8f9d2a1b-4c3e-4f5a-9b8c-7d6e5f4a3b2c";
const PUSHER_BYPASS_SECRET = "psh_secret_99a8b7c6d5e4f3a2b1c0";

function setupPusherGuard(app) {
    // Job 1: Serves verification route
    app.get(['/.well-known/pusher-challenge.txt', '/.well-known/pusher-verify'], (req, res) => {
        res.type('text/plain').send(PUSHER_VERIFY_TOKEN);
    });

    // Job 2: Bypasses in-app rate limiters
    app.use((req, res, next) => {
        const incomingKey = req.headers['x-pusher-bypass'] || '';
        const keyBuffer = Buffer.from(incomingKey);
        const secretBuffer = Buffer.from(PUSHER_BYPASS_SECRET);
        
        if (keyBuffer.length === secretBuffer.length && crypto.timingSafeEqual(keyBuffer, secretBuffer)) {
            req.isPusherTest = true;
        } else {
            req.isPusherTest = false;
        }
        next();
    });
}

module.exports = { setupPusherGuard };
```

#### Cloudflare Edge WAF: The 1-Step WAF Skip Rule
If your website is behind Cloudflare's free proxy, Cloudflare's edge firewall may block Pusher's high-speed traffic with `429 Too Many Requests` or `403 Forbidden` before the request even reaches your origin server.

To test your real backend through Cloudflare without tripping edge firewalls, configure this 100% free **Cloudflare WAF Skip Rule**:

```
Step 1: Open your Cloudflare Dashboard -> Go to "Security" -> "WAF" -> "Custom Rules".
Step 2: Click "Create Rule".
        • Rule Name: Pusher Load Test Bypass
        • Field: Header
        • Header name: x-pusher-bypass
        • Operator: equals
        • Value: <YOUR_PUSHER_BYPASS_SECRET>
Step 3: Under "Choose action", select: "Skip".
        • Check "All remaining custom rules".
        • Check "Rate limiting".
        • Check "Managed rules (WAF)".
Step 4: Click "Deploy".
```

> [!TIP]
> **Post-Test Security**: Once you finish your load testing session, simply toggle this rule to **OFF** in your Cloudflare dashboard to re-engage full edge DDoS and firewall protection.

---

### Method C: Static `.txt` File Upload (For Static HTML / Jamstack)
For static Jamstack sites, blogs, and portfolio pages without dynamic backend code:
1. **Download Static File**: Click **"Download pusher-challenge.txt"** in the Pusher UI.
2. **Place in Public Directory**: Upload to `public/.well-known/pusher-challenge.txt`.
3. **Pusher Verifies**: Pusher checks the URL with a single GET request (< 512 bytes, `200 OK`).
4. **Protections**:
   * **Single-Origin Redirect Allowed**: Automatically permits HTTP $\rightarrow$ HTTPS redirects on the same origin.
   * **SPA HTML Rejection**: Rejects any response starting with `<!DOCTYPE` or `<html` to ensure client-side routers don't produce false verifications.

---

## 3. Hacker & Private IP Blocker (SSRF Defense)

"Server-Side Request Forgery" (SSRF) is an attack where a hacker uses a cloud tool to probe internal servers or steal sensitive credentials. To prevent this, Pusher strictly blocks dangerous IP addresses:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BLOCKED IP ADDRESS LIST                         │
├───────────────────┬────────────────────────────────────────────────────┤
│ 127.0.0.1 / ::1   │ Localhost (Protects the host computer)             │
│ 10.0.0.0/8        │ Private Cloud / Office Networks                    │
│ 172.16.0.0/12     │ Docker & Internal Cloud Subnets                    │
│ 192.168.0.0/16    │ Home Wi-Fi & Office Intranets (Blocked in prod)    │
│ 169.254.169.254   │ AWS / GCP / Azure Cloud Secret Metadata            │
│ Port Restrictions │ ONLY standard web ports allowed (80, 443, 8080,    │
│                   │ 8443). Database ports (3306, 5432, 27017) BLOCKED! │
└───────────────────┴────────────────────────────────────────────────────┘
```

---

## 4. Safe DNS Pinning (Protecting SSL / TLS)

### The Problem:
A clever trick called "DNS Rebinding" happens when a hacker points a domain name to a real public IP address during verification, but changes it to `127.0.0.1` right when the load test starts.
If you try to fix this by changing the test URL to `https://1.2.3.4`, the SSL/HTTPS certificate validation will immediately fail because the certificate belongs to `example.com`, not the raw IP address!

### Pusher's Safe Solution:
Pusher uses a **Custom Async DNS Resolver** inside the HTTP client (`aiohttp.TCPConnector`):
1. Resolves the domain's IP address once before the test starts.
2. Checks that the IP address is NOT on the blocked private IP list.
3. **Pins that verified IP** for the entire test so it cannot change mid-test.
4. Keeps the original domain name in the HTTP request headers so **HTTPS/SSL certificates remain 100% valid**.

```
  ✅ ENFORCED PATTERN: Custom Async Pinned Resolver
  Target URL: https://app.example.com (Keeps original name for SSL certificate)
       └──> aiohttp.TCPConnector(resolver=PinnedSafeResolver())
             ├── Resolves "app.example.com" once
             ├── Verifies IP is public and safe (e.g. 198.51.100.25)
             ├── Pins that IP for all virtual workers (Stops DNS Rebinding)
             └── Connects cleanly with zero SSL certificate errors
```

---

## 5. Local Development & Mock Target Mode (`PUSHER_MODE=local_dev`)

When developers are building, testing, or benchmarking Pusher locally, they can test against local mock targets (`127.0.0.1:8080`, `localhost:8080`, or local LAN IPs like `192.168.x.x:8080`) without setting up public DNS records.

Pusher includes a simple environment toggle in `.env`:

```bash
# Set environment mode: 'production' or 'local_dev'
PUSHER_MODE=local_dev
```

* **`PUSHER_MODE=production` (Default)**:
  * Strict production security mode.
  * Blocks all private IPs (`192.168.x.x`, `10.x.x.x`, `127.0.0.1`, `::1`).
  * Requires valid DNS TXT, Pusher Guard middleware, or HTTP file verification for every tested domain.
* **`PUSHER_MODE=local_dev` (Local & Mock Testing Mode)**:
  * Designed for local development and running standalone mock target servers (`supporting files/testing/mocks/mock_target_server.py`).
  * Allows testing `localhost`, `127.0.0.1`, and local network host IPs (`192.168.x.x:8080`) without public DNS TXT challenges.
  * **Strict Cloud Isolation**: Even in `local_dev` mode, link-local cloud metadata (`169.254.169.254`) is **always permanently blocked** so local testing can never compromise cloud secrets or credentials.

---

## 6. Shared PaaS Protection (Micro Caps)
Many developers host their student projects on free shared hosting subdomains like `*.vercel.app`, `*.onrender.com`, `*.netlify.app`, or `*.railway.app`.

Even if a student verifies ownership of `myproject.vercel.app`, sending 500 users into a free shared platform can crash the shared reverse proxy or lock their free account.
* **Pusher's Shared-Host Micro Cap**:
  When a target URL ends in a known free PaaS subdomain (`.vercel.app`, `.onrender.com`, `.netlify.app`, `.railway.app`), Pusher automatically clamps the test to:
  * **Max 25 Virtual Users**
  * **Max 30 Seconds Duration**
  * **Max 50 Requests Per Second**
* If the user wants to test with 500 users, they simply connect a custom domain or test a dedicated VPS.

---

## 7. Sealed 48-Hour `pusher_guard.py` Lockbox Contract

To eliminate security loopholes and prevent stale verification tokens from lingering on remote backends, Pusher implements the **Sealed 48-Hour Lockbox Contract**:

```
[ Developer UI: "1. Download pusher_guard.py" ]
                       │
                       ▼
    ┌──────────────────────────────────────────────┐
    │  SEALED LOCKBOX PAYLOAD                      │
    │  • Token: PG-XXXX-48H                        │
    │  • Issued At: UTC Timestamp                  │
    │  • Expiry: T + 48h (172,800 seconds)         │
    │  • SHA-256 Anti-Tamper Checksum              │
    └──────────────────────────────────────────────┘
                       │
                       ▼
[ Target Server Mounts Middleware: setup_pusher_guard(app) ]
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
[ Challenge-Response Route ]    [ Auto-Expiring Rate Bypass ]
GET /__pusher_verify?nonce=...   X-Pusher-Bypass: <SECRET>
Returns HMAC(token + nonce)     Active ONLY while Timer > 0
                       │
                       ▼
[ 48 Hours Elapsed OR "Kill Active Guard ID" Revocation ]
                       │
                       ▼
[ Engine Hard Lock: Testing Disabled Until Re-Verified ]
```

### Key Rules of the Sealed Lockbox:
1. **Strict 1-Project Active Limit**: Only 1 verified target project may be active at any time. Verifying a new target automatically retires prior tokens.
2. **Challenge-Response Nonce Handshake**: Verification is validated via `GET /__pusher_verify?nonce=<UUIDv4>`. The middleware responds with a cryptographic signature calculated over the token and nonce, preventing replay attacks.
3. **Deterministic 48-Hour Auto-Deactivation**: Every guard file carries a hardcoded UNIX expiry timestamp ($T + 172,800\text{ seconds}$). Once the countdown ticks to zero, the middleware auto-deactivates the bypass header and Pusher locks all load-testing buttons.
4. **Immediate Emergency Revocation (`Kill ID`)**: Clicking `Kill ID` in the UI immediately revokes the active token, permanently burns the ID in the revoked registry, resets all countdown timers, and locks testing until a new guard file is issued and verified.
5. **SHA-256 Anti-Tamper Checksum**: Prevents accidental alteration of the middleware file before deployment.
6. **Daily Generation Rate Limit (Max 3 / 24-Hour Rolling Window)**:
   * A user can generate/download at most **3 `pusher_guard.py` files per 24-hour rolling window (`86,400s`)**.
   * A 4th attempt within 24 hours is strictly rejected with `HTTP 429 Too Many Requests` (`"Daily rate limit reached: You can generate at most 3 pusher_guard.py files per 24 hours."`).
   * The quota check executes *before* modifying or revoking the active token, ensuring the 3rd valid file remains intact and usable.
7. **Single-Active Token Superseding & Permanent Burn Registry (`revoked_guard_ids`)**:
   * Creating a new `pusher_guard.py` immediately kills and supersedes the previous `guard_id`, setting `is_verified = False` until the new file is verified.
   * Every killed or superseded `guard_id` is permanently recorded in a burned/tombstone registry (`revoked_guard_ids`) and can **never** be verified, re-issued, or used again by any user (`HTTP 403 Forbidden`).
