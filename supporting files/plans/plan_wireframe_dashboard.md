# Technical Plan: Black & White Wireframe Dashboard with Complete Business Logic

## Context & Objectives
Build a fully interactive, production-grade black-and-white wireframe interface for `DashboardPage.jsx` adhering strictly to:
- Black borders: `border-2 border-black`
- White background: `bg-white`
- Black text: `text-black`
- Zero color palette (inverted active states `bg-black text-white`)
- High-fidelity wireframe layout corresponding to hand-drawn architecture sketches.

## Key Subsystems
1. **Top Header Bar**: System telemetry status, memory cap (250MB), OS file descriptors cap (70%), and `•••` action dropdown.
2. **Left Navigation Sidebar**: 5 interactive tabs and system guardrail specifications box.
3. **Box 1 (Target Verification & 48h Guard Timer)**: SSRF filtering, downloadable Python middleware generator (`pusher_guard.py`), ticking 48-hour timer (`47:59:59`), and token revocation.
4. **Box 2 (Traffic Setup & Safety Controls)**: 3 load progression modes (`Step-Ramp`, `Sudden Rush`, `Steady Crowd`), 10-1000 VU slider, duration buttons, dynamic RAM estimator (`34 + Math.round(vus * 0.04) MB`), and armed launch/abort controls.
5. **Box 3 (Live Telemetry & Run History)**: 1-second interval telemetry generator (VUs, RPS, p95 latency, error rates), `Simulate 429 WAF Spike` circuit breaker trip, and run history table.
