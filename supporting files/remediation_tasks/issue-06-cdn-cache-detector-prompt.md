# ISSUE-06 Execution Prompt — Implement CDN Cache Detector & Warning Banner

- **Issue ID:** `ISSUE-06`
- **Priority:** Should Fix
- **Master Report:** [master_issue_report.md](./master_issue_report.md)

## Problem
`architecture_and_standards.md` specifies a CDN Cache Detector: if responses consistently return edge-cache headers (e.g., `cf-cache-status: HIT`, `x-vercel-cache: HIT`, `x-cache: ...HIT...`, or Fastly `x-fastly-request-id` + positive `x-cache-hits`) on `> 50%` of requests (`>= 20` requests), the platform must warn the user that they are benchmarking a CDN edge cache instead of their origin server.

## Implementation Steps
1. Add `is_cdn_cache_hit(headers) -> bool` in `backend/core/http_runner.py` and invoke an optional `on_cache_hit: Callable[[], None] | None = None` callback inside `AiohttpLoadClient.execute_request(...)` (preserving its 4-tuple return signature cleanly).
2. Track `cache_hit_count` across `worker_process.py` deltas, `LoadEngine._read_response()` (both Aiohttp & httpx paths), and `LoadEngine._apply_worker_delta()`. Compute `cache_hit_pct` and `cdn_cache_warning` (`total_requests >= 20 and cache_hit_pct > 50.0`) in `LoadEngine.get_status()` and `_finish_run()`.
3. Persist `cache_hit_count`, `cache_hit_pct`, and `cdn_cache_warning` in `backend/core/database.py` (`test_runs` schema migration) and `backend/core/report_service.py` (`save_run`, `_SUMMARY_FIELDS`, `_normalize_run_dict`).
4. Surface an amber CDN Cache Detector warning banner on live/idle `OverviewBoxes.jsx` (`DashboardPage.jsx` props) and `ReportsView.jsx` when `cdn_cache_warning` is true.
5. Add unit & end-to-end load engine tests in `supporting files/testing/unit/test_remediation_fixes.py` proving CDN hit headers trigger `cdn_cache_warning: True` and persist in `test_runs`, while `MISS`/origin headers stay `False`.
