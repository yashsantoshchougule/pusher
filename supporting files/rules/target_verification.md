# Target Verification & Abuse Prevention Rules

## 1. Why Domain Verification is Mandatory
Load-testing tools generate hundreds or thousands of web requests per minute. If anyone could type in any website address and hit "Start", malicious actors could use Pusher as an attack weapon to perform a **Distributed Denial of Service (DDoS)** attack against schools, governments, or competing businesses.

**Pusher's Core Security Law**: You can only test a website if you can prove that you own it or have administrative control over it. Pusher will never fire a single load-testing request at an unverified website.

---

## 1.1 URL and DNS readiness

The Verify Target page calls POST /api/target/validate-url. Pusher validates the URL and checks its DNS addresses. DNS_READY means a Guard can be generated for the origin. Ownership is confirmed only after the Guard challenge succeeds. Application requests and edge diagnostics require an active verification for that origin.

---

## 2. Live target ownership

Pusher currently supports the Python Guard ownership route. DNS TXT and standalone static-file proofs remain design options.

### Install the Pusher Guard

Generate the current Python artifact for the target. Compare its SHA-256 to the checksum shown by Pusher before installing it. Keep the file private and preserve its bytes during transfer. Install it during application startup.

```python
from pusher_guard import setup_pusher_guard

setup_pusher_guard(app)
```

The Guard adds one ownership verification route. Ordinary target requests use the app's authentication, authorization, CSRF protections, and rate limits. For an authenticated benchmark, provide ordinary test credentials in a journey. Use staging and choose an approved traffic budget for capacity testing.

If a target has an older Guard, revoke its registration in Pusher, remove the old artifact and middleware from the target, install a newly generated file, and verify ownership again. Pusher's controller cannot uninstall an artifact from your target.

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

## 5. Local development and sandbox

Use PUSHER_MODE=local_dev with the built-in loopback sandbox. For offline authentication, also set PUSHER_OFFLINE_DEV=true and bind Pusher to loopback. Standalone mock targets must match a loopback origin explicitly allowed by PUSHER_SANDBOX_ORIGINS. The default list includes http://127.0.0.1:8080 and http://localhost:8080. See the [project README](../../README.md) for startup and smoke checks.

Use PUSHER_MODE=production on shared deployments. Live targets require Guard ownership proof, with private and loopback addresses rejected.

---

## 6. Shared hosting

Check your provider's terms and agreed test quotas before testing a shared host. Earlier PaaS-specific micro caps are a design proposal. The current engine enforces its implemented resource limits and circuit breakers.

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
[ Target Server Registers Ownership Route: setup_pusher_guard(app) ]
                       │
[ Challenge-Response Route ]
                       │
                       ▼
[ 48 Hours Elapsed OR "Kill Active Guard ID" Revocation ]
                       │
                       ▼
[ Engine Hard Lock: Testing Disabled Until Re-Verified ]
```

### Key Rules of the Sealed Lockbox:
1. **Strict 1-Project Active Limit**: Only 1 verified target project may be active at any time. Verifying a new target automatically retires prior tokens.
2. **Challenge-response handshake**. Pusher verifies a fresh ownership response against the issued origin and artifact digest.
3. **Deterministic 48-Hour Auto-Deactivation**: Every guard file carries a hardcoded UNIX expiry timestamp ($T + 172,800\text{ seconds}$). Once the countdown ticks to zero, the ownership route rejects verification and Pusher locks all load-testing buttons.
4. **Immediate Emergency Revocation (`Kill ID`)**: Clicking `Kill ID` in the UI immediately revokes the active token, permanently burns the ID in the revoked registry, resets all countdown timers, and locks testing until a new guard file is issued and verified.
5. **SHA-256 Anti-Tamper Checksum**: Prevents accidental alteration of the middleware file before deployment.
6. **Daily Generation Rate Limit (Max 3 / 24-Hour Rolling Window)**:
   * A user can generate/download at most **3 `pusher_guard.py` files per 24-hour rolling window (`86,400s`)**.
   * A 4th attempt within 24 hours is strictly rejected with `HTTP 429 Too Many Requests` (`"Daily rate limit reached: You can generate at most 3 pusher_guard.py files per 24 hours."`).
   * The quota check executes *before* modifying or revoking the active token, ensuring the 3rd valid file remains intact and usable.
7. **Single-Active Token Superseding & Permanent Burn Registry (`revoked_guard_ids`)**:
   * Creating a new `pusher_guard.py` immediately kills and supersedes the previous `guard_id`, setting `is_verified = False` until the new file is verified.
   * Every killed or superseded `guard_id` is permanently recorded in a burned/tombstone registry (`revoked_guard_ids`) and can **never** be verified, re-issued, or used again by any user (`HTTP 403 Forbidden`).
