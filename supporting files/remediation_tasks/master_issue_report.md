# PUSHER Deep Audit Master Issue Report

**Audit Date:** 2026-11-26  
**Baseline:** `py -m pytest "supporting files/testing/unit" -q` -> 224 passed; live stress tests exposed critical runtime crashes under default `500 MB` RAM and `2,000–5,000` VU bursts plus missing rule features.

## Priority 1 — Critical Errors & Near-Crash Issues (Must Fix)
1. **ISSUE-01 — Default `500 MB` RAM Limit Crashes Multi-Process Tests (`128+` VUs):** `load_engine.py` spawns 7 Python worker processes on `500 MB` assuming `55 MB` per process, reaching ~556 MB RSS at startup and tripping `TRIPPED (RAM exceeds 500 MB limit)`.
2. **ISSUE-02 — High-VU Bursts (`2,000–5,000` VUs) Trip Falsely on 5 Transient Socket Drops:** `CircuitBreakers` stops entire high-concurrency tests on 5 global `status == 0` burst drops alongside un-staggered `Steady Crowd` wave connect spikes.
3. **ISSUE-03 — Broken `.venv` Virtual Environment:** `.venv\Scripts\python.exe` lacks `aiohttp`, `winloop`, `reportlab`, and `pytest`.
4. **ISSUE-04 — Missing `X-Pusher-Device-ID` CORS Header & Port `3001` Origin Support:** `main.py` omits `X-Pusher-Device-ID` from `allow_headers`; `config.py` omits fallback dev port `3001` and custom `PUSHER_ALLOWED_ORIGINS`.

## Priority 2 — Features Not Working Properly or Missing vs. Rules (Should Fix)
5. **ISSUE-05 — Missing Client Disconnect Guard (15s Auto-Abort):** Closing browser tabs leaves tests running unattended until duration expires.
6. **ISSUE-06 — Missing CDN Cache Detector (`cf-cache-status`, `x-vercel-cache`, `x-cache`, `x-fastly-request-id`):** No warning banner when >50% of responses are CDN cache hits.
7. **ISSUE-07 — Frontend Bundle Size Warning (`609.88 kB` > `500 kB`) & `51 MB` RAM Parity:** Monolithic `DashboardPage` chunk exceeds 500 kB; `profile` allows 50 MB while `load_router` requires `>= 51 MB`.
8. **ISSUE-08 — Unused Tailwind Tokens, Auth/Offline UX Clarity & Full E2E Re-Verification:** Clean unused `tailwind.config.js` tokens while preserving Olive/Cream login and Light/Dark dashboard modes, restore live servers (`8000`/`3000`), and verify end-to-end.
