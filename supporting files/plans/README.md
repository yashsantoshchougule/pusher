# Project Architecture & Implementation Plans

This folder stores all architectural plans, technical design specifications, and feature roadmaps for **Pusher**.

---

## 📋 Plan Naming Convention

Every plan created for the project follows this self-describing format:

```text
plan_<feature_or_component_description>.md
```

### Examples:
- `plan_scalable_core_and_plugin_architecture.md` — Technical blueprint for Frozen Core and plug-and-play plugins.
- `plan_2in1_pusher_guard_middleware_upgrade.md` — Specification for the verification and rate-limit bypass middleware.
- `plan_2person_team_collaboration_and_wifi_testing.md` — 2-person Git boundaries, API contracts, and local Wi-Fi testing.
- `plan_rules_and_security_loophole_hardening.md` — Initial audit hardening for SSRF, memory caps, and circuit breakers.

---

## 🗂️ Index of Current Plans

| Plan File | Purpose & Scope |
| :--- | :--- |
| [`plan_scalable_core_and_plugin_architecture.md`](plan_scalable_core_and_plugin_architecture.md) | Scalable Core + Plugin architecture blueprint with exact feature and memory rule mappings. |
| [`plan_2in1_pusher_guard_middleware_upgrade.md`](plan_2in1_pusher_guard_middleware_upgrade.md) | 2-in-1 `pusher_guard.py` / `pusherGuard.js` middleware and Cloudflare WAF skip rules. |
| [`plan_2person_team_collaboration_and_wifi_testing.md`](plan_2person_team_collaboration_and_wifi_testing.md) | Division of labor, Git branch rules (`backend-dev` / `frontend-dev`), and 2-laptop Wi-Fi setup. |
| [`plan_rules_and_security_loophole_hardening.md`](plan_rules_and_security_loophole_hardening.md) | Deep audit of SSRF defenses, memory limits (<250MB), and circuit breakers. |

---

> **Note**: Whenever an implementation plan is formulated, it will automatically be documented here in clean Markdown for permanent review and tracking.
