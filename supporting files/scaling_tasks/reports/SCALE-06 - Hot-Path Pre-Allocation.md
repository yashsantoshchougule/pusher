# SCALE-06 - Pre-Allocate Static Headers, Parsed URLs & Cache-Buster Fast Path

**Master Tracker:** [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md)
**Saved Plan & Prompt:** [SCALE-06-preallocate-hotpath-templates.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/plans/SCALE-06-preallocate-hotpath-templates.md)

---

## Issue
- **ID & Priority:** `SCALE-06` — `Should Fix`
- **Symptom & Impact:** Hot-loop requests allocated fresh `journey_request_headers()` dicts, recalculated `"?" in url` + `time.time()` for cache-busters, and ran regex/JSON/URL validation in `build_journey_request()` even for completely static journey steps. Multi-process workers also lacked a worker-ID namespace in `_cb=` nonces.

## How It Occurred
`LoadEngine._vu_worker`, `LoadEngine._vu_journey_worker`, and `_ProcessWorkerRunner` rebuilt static headers, URL prefixes, and step request payloads inside the per-request inner loop.

## How It Was Solved
- **[MODIFY] [journey_service.py](file:///c:/yash/projects/pusher/backend/core/journey_service.py)**: Added `CompiledJourneyStep` + `compile_journey_step()` pre-validating static URLs, computing cache-buster prefixes, separating static vs templated headers, and pre-encoding static UTF-8 JSON/text request bodies once per run.
- **[MODIFY] [load_engine.py](file:///c:/yash/projects/pusher/backend/core/load_engine.py)** & **[worker_process.py](file:///c:/yash/projects/pusher/backend/core/worker_process.py)**: Pre-allocated `_static_headers`, `_cb_prefix` (namespaced with `worker_id` across worker processes), and compiled journey steps once per run/worker.

## Testing
- **Targeted Tests (`test_hotpath_preallocation.py`, `test_stage4_api_journey.py`, `test_journey_extraction.py`, `test_target_privacy.py`):** **`30 passed in 5.31s`** (verifying static object reuse, exact templated parity, SSRF origin rejection, and speedup over uncompiled `build_journey_request`).
- **Full Python Suite:** `py -m pytest "supporting files/testing/unit" -q --tb=short`: **`217 passed, 40 warnings in 32.02s`** (exit `0`).
- **Node & Verification Suites:**
  - `node --test --test-timeout=15000 "supporting files/testing/unit/test_*.mjs"`: **`98 passed, 0 failed`**
  - `node "supporting files/testing/unit/test_time_mapping.cjs"`: **`10/10` passed**
  - `check_local_sandbox.py` & `check_flask_guard.py`: both passed (exit `0`)
  - `npm --prefix frontend run build`: built `1533` modules cleanly in `8.01s` (exit `0`)
- **Final Scaling Benchmark (`bench_final_scaling.py` against local `aiohttp.web` server, 4 KB payload):**
  - `64` VUs single-process (`3.05s`): **`4,034` requests, `0` failed, `1,324.3 RPS`, `p95_ms = 36 ms`**
  - `160` VUs multi-process (`5.58s` wall incl. spawn): **`15,043` requests, `0` failed, `2,694.5 RPS` wall (~5k+ RPS active), `p95_ms = 29 ms`, `peak_vus = 146`**

## Result
- **Status:** `Resolved`
- Passed all `SCALE-06` and full end-to-end verification gates.
