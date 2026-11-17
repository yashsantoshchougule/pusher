# Plan: Pusher Mission Control Dashboard (DashboardPage.jsx)

## Overview
Build a production-grade, highly responsive, and dark-themed **Mission Control Dashboard** (`src/pages/DashboardPage.jsx`) for **PUSHER**, adhering strictly to the official 5-color developer theme (`#011425`, `#16222A`, `#242424`, `#1F4959`, `#5C7C89`, `#FFFFFF`). Wire this page into `src/App.jsx` so submitting the authentication form on `LoginPage.jsx` navigates directly to the dashboard, and the user can interactively test traffic modes, view real-time guardrail metrics, and inspect historical runs.

---

## Architecture Components

1. **Left Sidebar (`w-64 bg-[#16222A]`)**:
   - PUSHER brand header and version badge (`v1.0 Open Source`).
   - Nav items: Overview, Verify Target, Traffic Setup, API Builder, Live Center, Reports, Compare, WAF Guide.
   - Bottom System Guardrail widget: Memory `38 MB / 250 MB Max (4KB Chunk Discard Active)` + Concurrency Cap (`70% OS File Descriptors`).

2. **Top Header Bar**:
   - Title `"Mission Control Dashboard"`.
   - Status pill `"Engine Ready • Local Async Worker"`.
   - Action: `"+ New Load Test"`.

3. **4 KPI Cards**:
   - Verified Targets (`2 Active Domains`)
   - Knee of the Curve (`420 Virtual Users`)
   - Peak Throughput (`1,240 RPS`, `p95 Latency: 162 ms`)
   - Safety Circuit Breakers (`Armed`)

4. **Interactive Traffic Launcher & Target Guard**:
   - Left (8 Cols): 3 Traffic Modes (`Step-Ramp`, `Sudden Rush`, `Steady Crowd`), VUs Slider (`10 - 1000`), Duration, Start Button.
   - Right (4 Cols): `pusher_guard.py` status, 48h countdown, SSRF protection indicator.

5. **Recent Load Test Runs Table**:
   - Columns: Target URL, Traffic Mode, Virtual Users, Peak RPS, p95 Latency, Safety Status, Actions.
