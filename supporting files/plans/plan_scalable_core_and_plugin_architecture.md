# Implementation Plan: Scalable Core + Plugin Architecture Upgrade

This plan outlines the updates required across all 5 project rule files in `supporting files/rules/` to transition Pusher from a monolithic design into a **Scalable Frozen Core + Modular Plugin Architecture**.

---

## 1. Goal Description & Scope

Upgrade the documentation and architectural specifications across:
1. `supporting files/rules/architecture_and_standards.md`
2. `supporting files/rules/team_collaboration.md`
3. `supporting files/rules/github_workflow.md`
4. `supporting files/rules/target_verification.md`
5. `supporting files/rules/safety_limits.md`

### Core Principles Maintained:
- **Simple, Beginner-Friendly Language**: Clear explanations without unnecessary jargon.
- **₹0 Tech Stack**: Zero paid cloud services, proprietary APIs, or dedicated GPU requirements.
- **2-Laptop Local Wi-Fi Setup**: Laptop 1 (Pusher runner) $\leftrightarrow$ Laptop 2 (mock/app server).
- **Strict Testing Boundary**: All tests, mocks, prototypes, and benchmarks stay strictly in `supporting files/testing/`.
- **Strict Git Rule**: AI is 100% strictly forbidden from running `git commit`, `git merge`, `git rebase`, or `git push`. All version control commands are performed manually by the human team.

---

## 2. File-by-File Blueprint & Loophole Analysis

### Component 1: `architecture_and_standards.md`
- **Section 6 Overhaul**:
  - Replace current Section 6 with the **Scalable Core + Plugin Directory Blueprint**.
  - **Frozen Core vs. Scalable Plugins Philosophy**:
    - `backend/core/`: Invariant, unbreakable engine logic that never changes when new features are added:
      - `contracts.py` (Pydantic / TypedDict schemas for REST & SSE) `[Feature #1]`
      - `plugin_registry.py` (Dynamic registration & auto-discovery)
      - `orchestrator.py` (VU coroutine lifecycle & cancellation) `[Feature #1, #2]`
      - `socket_pool.py` (Persistent TCP pool, TCPConnector) `[Memory Rule 3.1]`
      - `stream_reader.py` (4KB non-buffering chunk reader) `[Memory Rule 3.2]`
      - `queue_lock.py` (Single-test execution lock) `[Feature #1]`
      - `ssrf_and_dns.py` (SSRF IP filter & DNS pinning) `[Feature #10]`
      - `health_and_disconnect.py` (500ms heartbeat & 15s client drop guard) `[Feature #13]`
      - `metrics_store.py` (Circular telemetry ring buffer & percentiles) `[Memory Rule 3.3, Feature #7]`
    - `backend/plugins/`: 5 extension folders where features are added in a single file via decorators:
      1. `traffic_modes/`: `step_ramp.py`, `sudden_rush.py`, `steady_crowd.py` `[Feature #2]`
      2. `request_builders/`: `basic_http.py`, `cache_buster.py` `[Feature #4]`, `multi_step_flow.py` `[Feature #5]`
      3. `breakers_and_detectors/`: `server_5xx_breaker.py`, `waf_429_breaker.py`, `latency_breaker.py` `[Feature #11]`, `cdn_detector.py` `[Feature #12]`
      4. `verifiers/`: `dns_txt_verifier.py`, `guard_file_verifier.py` `[Feature #9]`
      5. `advisors_and_exporters/`: `english_advisor.py` `[Feature #6]`, `csv_exporter.py`
    - `frontend/src/core_ui/` & `frontend/src/features/`: Clean modular separation of always-on UI controls from pluggable feature views.
  - **"How to Add Future Features in 1 File" Code Example**: Demonstrate how writing `@register_traffic_mode("spike_test")` automatically registers a new mode into the API and UI with zero changes to `core/`.

### Component 2: `team_collaboration.md` & `github_workflow.md`
- **Folder Ownership Division**:
  - **Partner 1 (`backend-dev`)**: Exclusively owns `backend/core/`, `backend/plugins/`, `backend/api/`, `supporting files/testing/prototypes/`, `supporting files/testing/benchmarks/`, and `supporting files/testing/unit/`.
  - **Partner 2 (`frontend-dev`)**: Exclusively owns `frontend/src/core_ui/`, `frontend/src/features/`, and `supporting files/testing/mocks/`.
- **API Contracts (Rule 2)**:
  - Contracts anchored in `backend/core/contracts.py`.
  - Added REST endpoints:
    - `GET /api/v1/plugins`: Dynamically returns loaded traffic modes, request builders, and breakers so the React UI populates automatically.
    - `POST /api/v1/verify/middleware`: Downloads pre-configured `pusher_guard.py` / `pusherGuard.js` with verification UUID & HMAC bypass key.
    - Standard `POST /api/v1/test/start`, `POST /api/v1/test/stop`, `GET /api/v1/test/status`.
  - Preserved WebSocket 1-second telemetry contract with active alerts and health metrics.

### Component 3: `target_verification.md`
- **2-in-1 Pusher Guard Middleware (`guard_file_verifier.py`)**:
  - Dual purpose: serves `GET /.well-known/pusher-challenge.txt` / `/.well-known/pusher-verify` and bypasses application rate limiters using `X-Pusher-Bypass` header checked with `hmac.compare_digest`.
  - **Cloudflare WAF 1-Step Skip Rule**:
    - Detailed, beginner-friendly instructions on how to bypass Cloudflare edge rate limiting when testing a live Cloudflare-proxied domain:
      * Cloudflare Dashboard $\rightarrow$ Security $\rightarrow$ WAF $\rightarrow$ Custom Rules $\rightarrow$ Create Rule.
      * Expression: `(http.request.headers["x-pusher-bypass"][0] eq "YOUR_SECRET_KEY")`.
      * Action: **Skip** (select "All remaining WAF components", "Rate Limiting", and "Managed Rules").
      * Deactivate rule after load testing is complete.

### Component 4: `safety_limits.md`
- **Slower-PC Friendly CPU Self-Check (`health_and_disconnect.py`)**:
  - Heartbeat interval relaxed from `100ms` to **`500ms`** to eliminate false triggers on entry-level dual/quad-core CPUs.
  - Takes a **1-second pre-test auto-baseline** during idle startup.
  - Warning banner at **`150ms–200ms`** drift above baseline.
  - Pauses VU scaling only if lag stays **`> 200ms` above baseline for 5 consecutive seconds**.
- **Firewall Bypass Troubleshooting Box (`waf_429_breaker.py` & `english_advisor.py`)**:
  - Prominent guide displayed whenever HTTP 429 or 403 blocks occur:
    1. *Option A (Backend Rate Limiter)*: Install 2-in-1 `pusher_guard.py` / `pusherGuard.js`.
    2. *Option B (Cloudflare / Cloud WAF)*: Add the 1-step Cloudflare WAF Skip Rule.
    3. *Option C (Zero-Firewall Local Testing)*: Run target on Laptop 2 using `PUSHER_MODE=local_dev` over Wi-Fi.

---

## 3. Verification Plan

1. **Rule File Integrity**: Check that all 5 files in `supporting files/rules/` contain complete, unabridged markdown.
2. **Path Verification**: Confirm that all paths consistently use `supporting files/` (with space) and test files remain strictly in `supporting files/testing/`.
3. **No Code Spills**: Confirm no `.py` or temporary files exist outside `supporting files/testing/`.
4. **Git Safety Check**: Confirm the AI executed zero Git commands.
