# `SCALE-06` Plan & Detailed Execution Prompt

- **Issue ID:** `SCALE-06` (Position 6 of 6 in [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md))
- **Exact Title:** Pre-Allocate Static Headers, Parsed URLs & Cache-Buster Fast Path
- **Priority:** `Should Fix`

---

## 1. Problem, Baseline & Confirmed Cause
- **Current bottleneck:** On every request iteration inside `_vu_worker` and `_vu_journey_worker` (`load_engine.py` and `worker_process.py`), the hot loop allocates a fresh `journey_request_headers()` dict, recomputes `append_cache_buster` (`time.time()`, `"?" in url`), and in journey mode runs full `build_journey_request()` (string regex substitution, `json.loads`/`dumps`, `journey_target()`) even for completely static journey steps.
- **Visible impact:** Unnecessary per-request Python dict/string/URL allocations increase GC pressure and CPU cost per RPS across thousands of concurrent requests/sec.
- **Expected behavior & Acceptance Criteria:**
  1. Single-URL `_vu_worker` reuses pre-allocated static base headers + pre-computed `_cb_prefix` (`f"{url}{'&' if '?' in url else '?'}_cb={run_epoch_ms}_"`) so per-request URL building is one fast `f"{cb_prefix}{vu_id}_{req_seq}"` formatting step (preserving `append_cache_buster()` helper cleanly for existing tests).
  2. `journey_service.py` exposes `CompiledJourneyStep` + `compile_journey_step(...)` which pre-validates static path URLs, pre-computes cache-buster prefix, separates static vs dynamic `{{var}}` headers, and pre-encodes static UTF-8 request bodies once per run start!
  3. Both `LoadEngine` and `_ProcessWorkerRunner` compile steps once before dispatching `_vu_journey_worker` and execute `compiled.render(...)` in the hot loop.
  4. All journey, privacy, validation, extraction tests (`test_stage4_api_journey.py`, `test_journey_extraction.py`, `test_target_privacy.py`, `test_stage2_load_engine.py`) + new `test_hotpath_preallocation.py` pass cleanly.

---

## 2. Affected Files
- `[MODIFY]` `backend/core/journey_service.py` — add `CompiledJourneyStep` and `compile_journey_step(step, base, is_sandbox)` with pre-encoded static body bytes, pre-separated static/dynamic headers, and pre-validated target URL/cb-prefix.
- `[MODIFY]` `backend/core/load_engine.py` & `backend/core/worker_process.py` — pre-allocate `_static_headers` & `_cb_prefix` for single-URL workers, and compile `self.journey_steps` once per run/worker for `_vu_journey_worker`.
- `[NEW]` `supporting files/testing/unit/test_hotpath_preallocation.py` — test compiled static/dynamic journey step parity vs `build_journey_request`, SSRF rejection preservation, and fast cache-buster generation speed.

---

## 3. Detailed Execution Prompt (Issue 6 — `SCALE-06`)

> **Task:** Pre-allocate static request headers, URL prefixes, and compiled journey step templates across `journey_service.py`, `load_engine.py`, and `worker_process.py`.
>
> **Exact Steps to Execute:**
> 1. In `backend/core/journey_service.py`: implement `CompiledJourneyStep` dataclass (`method`, `static_url`, `cb_sep`, `has_dynamic_path`, `raw_path`, `base`, `is_sandbox`, `static_headers`, `dynamic_headers`, `static_body`, `has_dynamic_body`, `raw_body`, `extract_key`, `expected_status`) + `compile_journey_step(step, base, is_sandbox)` and `CompiledJourneyStep.build(context, cache_bust, vu_id, req_seq, cb_epoch_ms)`. Verify identical behavior on `{{token}}` URL encoding, JSON/text bodies, SSRF origin validation, and missing-variable `JourneyInputError`.
> 2. Update `load_engine.py` and `worker_process.py` to cache `static_headers = journey_request_headers()`, `_cb_prefix`, and compiled journey steps once per run instead of re-allocating dicts and re-parsing static bodies/URLs on every request.
> 3. Add `supporting files/testing/unit/test_hotpath_preallocation.py` verifying compiled vs uncompiled output parity, error behavior, and fast formatting benchmark.
> 4. Run targeted + full `py -m pytest "supporting files/testing/unit" -q --tb=short` and save `SCALE-06 - Hot-Path Pre-Allocation.md`.
