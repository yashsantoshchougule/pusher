# Implementation Plan: Comprehensive Loophole Hardening for Pusher Rule Files

## Goal Description
Audit and upgrade all 5 core project specification rule files (`architecture_and_standards.md`, `memory_management.md`, `safety_limits.md`, `target_verification.md`, and `github_workflow.md`) plus the testing guide in `supporting files/testing/README.md`. 
The objective is to eliminate all technical, security, platform, and operational loopholes while preserving:
- Simple, beginner-friendly explanations (zero confusing jargon)
- The 100% Free (₹0) open-source requirement
- The 2-Laptop local Wi-Fi testing architecture (no public in-app demo sites)
- Strict human-only Git version control boundaries
- All existing ASCII diagrams and the exact directory layout (`supporting files/rules/`, `supporting files/testing/`, `frontend/`, `backend/`)

---

## User Review Required
> [!IMPORTANT]
> **No In-App Practice Site**: Confirmed that all practice/mock testing runs exclusively via `supporting files/testing/mocks/` on Laptop 2 or local host, never as a public route inside the deployed production UI.
> **Platform Portability (Windows vs POSIX)**: Addressed the Python `resource` module absence on Windows by defining cross-platform socket limits and event-loop adapters (`winloop` on Windows, `uvloop` on Linux).
> **Client Disconnect Handling**: Codified how the backend engine behaves if a user closes their browser or loses Wi-Fi mid-test.

---

## Identified Loopholes & Proposed Fixes

### 1. `architecture_and_standards.md` Loopholes
* **Loophole 1.1: Multi-Step Mode Data Handover Undefined**:
  * *Issue*: Feature 5 mentions chaining 2–3 requests (e.g. Login -> Dashboard) but doesn't define how a token is extracted from response 1 and injected into response 2.
  * *Fix*: Define simple JSONPath / key-value extraction rules (e.g., extract `token` from `{"token": "..."}` or cookies into `{{auth_token}}`) using lightweight regex/json without heavy dependencies.
* **Loophole 1.2: Cache Buster Randomizer Tags Unbounded**:
  * *Issue*: Feature 4 mentions `{{random_int}}` and `{{uuid}}` but lacks syntax bounds and repetition handling.
  * *Fix*: Specify `{{random_int(min, max)}}` (defaults to `1` to `1,000,000`) and `{{uuid}}` (UUIDv4 string) replaced per-virtual-user request iteration.
* **Loophole 1.3: Client WebSocket / Wi-Fi Disconnection Handling**:
  * *Issue*: If Laptop 1's browser disconnects or the user closes the tab mid-test, does the backend engine run indefinitely?
  * *Fix*: Define a 15-second client reconnect grace period; if no client heartbeat or WebSocket reconnects within 15 seconds, the engine triggers a graceful abort to free resources.
* **Loophole 1.4: 2-Laptop Local Firewall & Port Binding**:
  * *Issue*: Laptop 2 running mock servers often gets blocked by default Windows Defender Firewall on port 8080.
  * *Fix*: Add clear, beginner-friendly instructions on binding mock servers to `0.0.0.0` (all interfaces) and configuring a one-line Windows Firewall rule (`netsh advfirewall firewall add rule ...` or GUI prompt).

---

### 2. `memory_management.md` Loopholes
* **Loophole 2.1: Infinite Response Stream Memory Attack (Slowloris/Chunked Bomb)**:
  * *Issue*: A broken or slow target server could send infinite chunked bytes (`Transfer-Encoding: chunked`), causing the engine worker to stream forever.
  * *Fix*: Enforce a hard response byte ceiling (`max_response_body_bytes = 10 MB`). If a response exceeds 10MB, the stream is aborted, marked as `OVERSIZED_RESPONSE`, and counted without consuming further CPU/RAM.
* **Loophole 2.2: Windows Compatibility for OS File Descriptor Check**:
  * *Issue*: `resource.getrlimit(RLIMIT_NOFILE)` does not exist on Windows and raises `AttributeError: module 'resource' has no attribute 'getrlimit'`.
  * *Fix*: Specify cross-platform detection:
    ```python
    if sys.platform == "win32":
        # Windows default socket capacity or _setmaxstdio
        max_fds = 2048
    else:
        import resource
        soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        max_fds = soft
    ```
* **Loophole 2.3: Abandoned Test Queue Starvation**:
  * *Issue*: If User A starts a 5-minute test and User B enters the queue, then closes their tab, User B's queued job would run unnecessarily when User A finishes.
  * *Fix*: Queue entries require an active client SSE/WebSocket ping. If no ping is received for 30 seconds while in queue, the job is automatically evicted from the queue.

---

### 3. `safety_limits.md` Loopholes
* **Loophole 3.1: Alternating Error Blind Spot in Consecutive 5xx Breaker**:
  * *Issue*: If a server fails on every other request (`500, 200, 500, 200`), consecutive error count stays at 1 and never hits 5, even though 50% of requests are failing.
  * *Fix*: Clarify that the **Rolling Window Ratio Breaker** (>25% errors in rolling 5s window) handles alternating failures, and document the 5-bucket ring counter mechanism that tracks this in `< 10 KB` of RAM.
* **Loophole 3.2: False-Positive Breaker Trips on Low Sample Sizes**:
  * *Issue*: During the first 500ms of a test, if the very first request takes 8,100ms or fails, p95 would be 8,100ms on a sample size of 1, prematurely tripping the breaker.
  * *Fix*: Mandate a **Minimum Sample Size Barrier**: The latency breaker and rolling error ratio breakers cannot trip until at least **20 total requests** have been recorded in the current stage.
* **Loophole 3.3: Emergency Stop UI / Network Disconnect Race**:
  * *Issue*: If network latency delays the "Emergency Stop" HTTP request to the backend, the user might think it failed.
  * *Fix*: The UI immediately shows a "Halting Engine..." state and sends the abort signal over both the active WebSocket channel and a fallback REST endpoint `POST /api/v1/test/stop`.

---

### 4. `target_verification.md` Loopholes
* **Loophole 4.1: Single-Origin HTTP -> HTTPS Redirect Loophole**:
  * *Issue*: Modern websites automatically redirect `http://domain.com/.well-known/...` to `https://domain.com/.well-known/...` (HTTP 301/308). If redirects are forbidden, verification fails for standard HTTPS sites.
  * *Fix*: Explicitly permit exactly one redirect **if and only if** it stays on the exact same host and upgrades from `http://` to `https://`. Cross-domain redirects remain strictly forbidden.
* **Loophole 4.2: SPA Router HTML Interception**:
  * *Issue*: Single Page Apps (React/Vue/Next.js) often route all unknown URLs to `index.html` returning `200 OK` with HTML content.
  * *Fix*: The verification engine must verify that the body contains `pusher-verify=` and match the exact token value, explicitly verifying it is NOT an HTML document (`<!DOCTYPE html>` or `<html`).
* **Loophole 4.3: Local Dev Mode Subnet Leakage**:
  * *Issue*: In `PUSHER_MODE=local_dev`, how do we ensure Laptop 1 can reach Laptop 2 (`192.168.x.x`) without opening an SSRF hole to cloud metadata?
  * *Fix*: Codify that `local_dev` mode permits ONLY the local interface network (`192.168.0.0/16` or `10.0.0.0/8` on the active Wi-Fi adapter) while **strictly keeping AWS/GCP/Azure link-local metadata (`169.254.169.254`) and loopback blocked unless explicitly running mock targets**.
* **Loophole 4.4: DNS Propagation Timeout & Guidance**:
  * *Issue*: Beginners get confused when their DNS TXT record doesn't verify immediately due to DNS caching.
  * *Fix*: Document UI guidance explaining standard 60-second TTL propagation, providing a "Check DNS Status" retry button with automatic 5-second polling up to 3 attempts.

---

### 5. `github_workflow.md` Loopholes
* **Loophole 5.1: Merge Conflict Strategy Between Team Members**:
  * *Issue*: Member 1 (`backend-engine`) and Member 2 (`frontend-and-mocks`) might edit shared files (like project `README.md` or `.env.example`).
  * *Fix*: Specify clean merge etiquette: Feature branches merge into `main` via manual GitHub Pull Requests (PRs). Only the repository owner/team leader merges PRs after peer review.
* **Loophole 5.2: Secret Leak Prevention & Windows/macOS OS Files**:
  * *Issue*: Windows developers frequently commit `desktop.ini`, `Thumbs.db`, or `.env.local` by mistake.
  * *Fix*: Provide a ready-to-use `.gitignore` checklist and explicit commands for un-tracking accidentally staged files (`git rm --cached`).

---

## Proposed Changes to Rule Files

### [MODIFY] `supporting files/rules/architecture_and_standards.md`
- Add 2-Laptop setup instructions, Wi-Fi firewall commands, multi-step parameter passing syntax (`{{auth_token}}`), Cache Buster randomizer formulas (`{{random_int(min, max)}}`), WebSocket disconnect grace period (15s), and complete feature details.

### [MODIFY] `supporting files/rules/memory_management.md`
- Add response stream size ceiling (10 MB), cross-platform Windows vs Linux file descriptor detection, abandoned queue eviction policy (30s ping), and memory leak audit specifications.

### [MODIFY] `supporting files/rules/safety_limits.md`
- Add Minimum Sample Size Barrier (>= 20 responses before latency breaker can trip), rolling window sliding-bucket algorithm, and dual-channel Emergency Stop dispatch (WebSocket + REST).

### [MODIFY] `supporting files/rules/target_verification.md`
- Add single-origin HTTP->HTTPS redirect specification, SPA HTML rejection rule, locked local Wi-Fi SSRF boundaries for `local_dev` mode, and DNS propagation retry guidance.

### [MODIFY] `supporting files/rules/github_workflow.md`
- Add GitHub Pull Request review workflow for Member 1 and Member 2, merge conflict resolution steps, and comprehensive `.gitignore` protection rules.

### [MODIFY] `supporting files/testing/README.md`
- Ensure all directory paths and testing instructions align with the 2-laptop setup and testing folders (`mocks/`, `prototypes/`, `benchmarks/`, `unit/`).

---

## Verification Plan

### Automated / Manual Inspection
- Verify all 5 Markdown files contain zero technical loopholes and zero contradictory statements.
- Ensure all directory paths strictly match `supporting files/rules/` and `supporting files/testing/`.
- Ensure all ASCII diagrams render cleanly with zero syntax issues.
- Confirm complete adherence to the ₹0 free requirement and the strict AI Git constraint.
