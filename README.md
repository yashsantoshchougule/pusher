# Pusher 🚀

> **A high-speed, safe, and 100% free website load testing engine designed for real-time performance insights without cloud bills.**

---

## 🌟 What is Pusher?

**Pusher** is an open-source, asynchronous website load testing tool built for developers, indie hackers, and small engineering teams. It allows you to simulate hundreds of concurrent virtual users (VUs) against your web applications to find bottlenecks, measure latency (`p50`, `p90`, `p95`, `p99`), and discover your server's breaking point before your users do.

Built with a **₹0 (100% Free) requirement**, Pusher requires zero paid cloud services, zero external API keys, and runs efficiently on consumer hardware (16GB RAM laptops) consuming less than **500MB of RAM for 2,250 virtual users by default (scalable up to 75% of host RAM)**.

---

## ⚡ Key Highlights & Safety Features

- 🛑 **Mandatory Target Verification**: Prevents abuse by requiring domain ownership verification (via free DNS TXT records or the downloadable 2-in-1 Pusher Guard middleware).
- 🛡️ **2-in-1 Pusher Guard Middleware & 48-Hour Sealed Lockbox**:
  - Drop-in middleware for FastAPI, Flask, and Express that verifies domain ownership and bypasses in-app rate limiters.
  - **3/Day Rate Limiter**: Enforces a strict quota of at most 3 guard files per 24-hour rolling window (`HTTP 429 Too Many Requests`).
  - **Instant Superseding & Permanent ID Burn**: Generating a new file permanently burns the previous ID into `revoked_guard_ids`; revoked IDs can never be verified or used again (`HTTP 403 Forbidden`).
- ⚡ **3 Automatic Safety Circuit Breakers**:
  1. *Crash Breaker*: Instantly halts test on 5 consecutive 5xx errors or >25% error ratio.
  2. *Firewall (WAF) Breaker*: Stops immediately on HTTP 429 / 403 firewall challenges to protect your IP from blacklisting.
  3. *Latency Breaker*: Cuts test if `p95` latency exceeds 8 seconds.
- 🔴 **Instant Emergency Stop**: UI button halts all engine coroutines and closes sockets in under **200 milliseconds**.
- 💻 **Local Mock Target Testing (`PUSHER_MODE=local_dev`)**: Built-in mock target server (`mock_target_server.py`) allows testing 200 OK, 5xx crashes, and 429 WAF blocks safely without cloud bills or public DNS records.

---

## 📁 Repository Structure

```
pusher/
├── backend/                             # Fast asynchronous Python backend (FastAPI, asyncio)
├── frontend/                            # React + Vite + Tailwind CSS dashboard & live charts
├── supporting files/
│   ├── rules/                           # Strict architecture, safety, and team guidelines
│   │   ├── architecture_and_standards.md# System architecture, features, and standards
│   │   ├── memory_management.md         # RAM budget rules (<500MB default for 2,250 VUs, scalable)
│   │   ├── safety_limits.md             # 3 circuit breakers & SSRF defense
│   │   ├── target_verification.md       # DNS & 2-in-1 Pusher Guard verification
│   │   ├── github_workflow.md           # Git rules & AI safety constraints
│   │   └── team_collaboration.md        # Team collaboration & agile development standards
│   ├── plans/                           # Architecture blueprints & technical design plans
│   │   ├── README.md                    # Plan index and naming conventions
│   │   └── plan_*.md                    # Descriptive feature and implementation plans
│   └── testing/                         # All test scripts, benchmarks, and mock servers
│       ├── mocks/                       # Mock target server (200 OK, 500 crash, 429 WAF)
│       ├── prototypes/                  # Engine prototypes and validation scripts
│       ├── benchmarks/                  # Memory & throughput benchmark scripts
│       └── unit/                        # Unit tests for verification and safety logic
└── README.md
```

---

## 📖 Project Documentation & Rules

All core technical specifications and collaboration guidelines are organized inside `supporting files/rules/`:

1. [Architecture & Standards](supporting%20files/rules/architecture_and_standards.md) — Tech stack, system flowcharts, and 13 core features.
2. [Target Verification](supporting%20files/rules/target_verification.md) — DNS verification and the 2-in-1 Pusher Guard middleware.
3. [Safety Limits & Breakers](supporting%20files/rules/safety_limits.md) — Circuit breakers, SSRF IP blocking, and event-loop lag monitoring.
4. [Memory Management](supporting%20files/rules/memory_management.md) — Zero-leak streaming, circular metrics buffers, and RAM profiling.
5. [GitHub Workflow](supporting%20files/rules/github_workflow.md) — Branching strategy, manual git rules, and AI safety boundaries.
6. [Team Collaboration](supporting%20files/rules/team_collaboration.md) — Modular subsystems, flexible task ownership, and API contracts.

---

## 👥 Modular Subsystems & Flexible Roles

- **Backend & Engine Subsystem**: Fast async socket pool, domain verifier, Pusher Guard generator, circuit breakers.
- **Frontend UI Subsystem**: Live dashboard, Chart.js telemetry, Emergency Stop button, verification wizard.
- **Testing & Quality Subsystem**: Standalone mock target server, prototypes, benchmarks, and unit tests.

---

## 🔒 Safety & Ethics Notice

Pusher is strictly intended for **authorized testing on domains and servers that you own or have explicit written permission to test**. Testing unauthorized third-party infrastructure is strictly blocked by built-in domain ownership verification and SSRF IP filters.
