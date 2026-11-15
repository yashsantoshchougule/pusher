# Target Verification & Abuse Prevention Rules

## 1. Why Domain Verification is Mandatory
Load-testing tools generate hundreds or thousands of web requests per minute. If anyone could type in any website address and hit "Start", malicious actors could use Pusher as an attack weapon to perform a **Distributed Denial of Service (DDoS)** attack against schools, governments, or competing businesses.

**Pusher's Core Security Law**: You can only test a website if you can prove that you own it or have administrative control over it. Pusher will never fire a single load-testing request at an unverified website.

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
When testing a dynamic web application (built with FastAPI, Flask, Express, Django, etc.), developers face a common frustration: **their own in-app rate limiters** block the load test after 50 to 100 requests with `HTTP 429 Too Many Requests`.

To solve this, Pusher's verifier plugin (`backend/plugins/verifiers/guard_file_verifier.py`) provides a downloadable **2-in-1 Server Middleware File** (`pusher_guard.py` for Python or `pusherGuard.js` for Node.js).

#### Why a Backend File Beats a Public `.txt` File:
* A public `.txt` file can be opened by anyone in a browser, so you can **never** put a secret rate-limit bypass key inside it.
* A backend middleware file (`.py` or `.js`) runs privately inside your server. Visitors and hackers cannot read the code, so it safely holds both the **Public Verification Token** AND a **Private Rate-Limit Bypass Secret**!

#### The Two Jobs of the 2-in-1 Guard File:
1. **Job 1 (Automatic Domain Verification)**:
   The middleware automatically registers the `GET /.well-known/pusher-challenge.txt` (and alias `GET /.well-known/pusher-verify`) route on your web server and returns your unique `pusher-verify=<UUIDv4>` token.
2. **Job 2 (Automatic Backend Rate-Limiter Bypass)**:
   During an active load test, Pusher automatically injects a secret HTTP header on every single request:
   `X-Pusher-Bypass: <PRIVATE_HMAC_SECRET>`
   The middleware checks this header using constant-time comparison (`hmac.compare_digest`). If it matches, it flags `request.state.is_pusher_test = True` (or `req.isPusherTest = true`), allowing your application-layer rate limiter (like SlowAPI or express-rate-limit) to skip blocking the test!

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

## 7. Verification Token Lifetime
* **Token Expiration**: Verification tokens expire in **72 hours** if not verified.
* **Monthly Re-Check**: Verified domains remain valid for **30 days** before requiring a quick re-check.
