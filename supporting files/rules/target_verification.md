# Target Verification & Abuse Prevention Rules

## 1. Why Domain Verification is Mandatory
Load-testing tools generate hundreds or thousands of web requests per minute. If anyone could type in any website address and hit "Start", malicious actors could use Pusher as an attack weapon to perform a **Distributed Denial of Service (DDoS)** attack against schools, governments, or competing businesses.

**Pusher's Core Security Law**: You can only test a website if you can prove that you own it or have administrative control over it. Pusher will never fire a single load-testing request at an unverified website.

---

## 2. The Two 100% Free Verification Methods

Pusher offers two simple, 100% free ways to prove domain ownership:

```
               [ User Enters Target Website: https://app.example.com ]
                                        │
                         Selects Verification Method
                                        │
                ┌───────────────────────┴───────────────────────┐
                ▼                                               ▼
     [ Method A: DNS TXT Challenge ]             [ Method B: 1-Click File Download ]
                │                                               │
  Add TXT at:                                   Click "Download Verification File"
  _pusher-challenge.app.example.com             Upload pusher-challenge.txt to:
  Value: pusher-verify=<UUIDv4>-<HMAC>          https://app.example.com/.well-known/pusher-challenge.txt
                │                                               │
                └───────────────────────┬───────────────────────┘
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

### Method A: DNS TXT Challenge (Best for Custom Domains)
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

### Method B: 1-Click File Download (Best for Vercel, Render & Next.js)
For developers using platforms like Vercel, Render, or Netlify, editing DNS records can take time. Method B takes less than 60 seconds:

1. **Click "Download Verification File"**:
   Pusher provides a simple button in the UI:
   `[📥 Download pusher-challenge.txt]`
2. **Upload to Website**:
   The developer places this file in their web project's public folder so it can be viewed at:
   `https://<your-domain>/.well-known/pusher-challenge.txt`
3. **Pusher Checks the URL**:
   Pusher sends a single, lightweight HTTP GET request to that exact link:
   * Only reads the first 512 bytes.
   * Status code must be `200 OK`.
   * The text inside must match the token.
4. **Edge-Case Protections for File Verification**:
   * **Safe HTTP $\rightarrow$ HTTPS Redirect**: If the target server automatically redirects an insecure link (`http://`) to secure HTTPS (`https://`), Pusher permits exactly 1 redirect as long as it stays on the exact same domain name. Cross-domain redirects are strictly rejected.
   * **SPA Router Protection**: Modern frontend frameworks (React/Vue/Next.js) often return `index.html` (with a `200 OK` status) for missing files. Pusher checks that the response is NOT an HTML document (it rejects bodies starting with `<!DOCTYPE` or `<html`) to prevent false-positive verifications.
5. **Zero Paid Services**: Works on any free hosting service (Vercel free tier, Render free web service, GitHub Pages).

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

## 5. The 2-Laptop Local Development Mode (`PUSHER_MODE=local_dev`)

When the 2 teammates are developing and testing Pusher locally on their home Wi-Fi network, Laptop 1 needs to send test traffic to Laptop 2 (`192.168.1.50:8080`).

Pusher includes a simple environment toggle in `.env`:

```bash
# Set environment mode: 'production' or 'local_dev'
PUSHER_MODE=local_dev
```

* **`PUSHER_MODE=production` (Default)**:
  * Strict security mode.
  * Blocks all private IPs (`192.168.x.x`, `10.x.x.x`, `127.0.0.1`).
  * Requires valid DNS TXT or HTTP file verification for every domain.
* **`PUSHER_MODE=local_dev` (2-Laptop Team Mode)**:
  * Designed for the 2 teammates testing on local Wi-Fi.
  * Allows Laptop 1 to test Laptop 2's local IP address (`192.168.x.x:8080`) without public DNS records.
  * **Strict Cloud Isolation**: Even in `local_dev` mode, link-local cloud metadata (`169.254.169.254`) is **always permanently blocked** so a local config can never compromise cloud secrets.

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
