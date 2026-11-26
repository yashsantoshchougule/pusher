# `SCALE-02` Plan & Detailed Execution Prompt

- **Issue ID:** `SCALE-02` (Position 2 of 6 in [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md))
- **Exact Title:** Switch Hot-Path HTTP Engine from httpx/httpcore to aiohttp + winloop/uvloop
- **Priority:** `Must Fix`

---

## 1. Problem, Baseline & Confirmed Cause
- **Current bottleneck:** `worker_process.py` and `load_engine.py` execute every HTTP request on the hot path via `httpx.AsyncClient` + pure-Python `httpcore.AsyncConnectionPool` (plus `_ShardedAsyncConnectionPool` / `_ShardedStream` wrappers) running on Python's default `ProactorEventLoop` on Windows.
- **Visible impact:** Per-request Python object/URL/stream wrapper allocations and pure-Python HTTP/1.1 parsing limit per-process throughput and raise CPU usage under load compared to Cython `aiohttp` (`llhttp`) + `winloop`/`uvloop` (`libuv`).
- **Expected behavior & Acceptance Criteria:**
  1. `pyproject.toml` supports Python `>=3.12,<3.14` and declares `aiohttp>=3.14,<4`, `winloop>=0.8; sys_platform == 'win32'`, and `uvloop>=0.21; sys_platform != 'win32'`.
  2. New `backend/core/http_runner.py` implements:
     - `SSRFPinnedResolver(aiohttp.abc.AbstractResolver)` validating all resolved IPs via `target_policy.resolve_addresses(..., is_sandbox)` with configurable 60s DNS caching and converting resolution timeouts to `TimeoutError`/`DestinationTimeoutError`.
     - `_SSRFCheckedTCPConnector(aiohttp.TCPConnector)` validating literal/bare IP targets as well (blocking `127.0.0.1` / `169.254.169.254` / RFC1918 when `is_sandbox=False`), using `keepalive_timeout=30`, `limit=connections`, `limit_per_host=connections`, and `ttl_dns_cache=60`.
     - `AiohttpLoadClient` enforcing exact origin binding (`origin(url) == base_origin`), sandbox path checks, `allow_redirects=False`, pinned `"Host"` header, `4 KB` streaming chunk discard (`iter_chunked(4096)`), and the `10 MB` max response stream guard (`memory_management.md`).
  3. `worker_process.py` installs `winloop` (`winloop.new_event_loop` / `asyncio.run(..., loop_factory=...)` on Windows; `uvloop` on POSIX; clean fallback) and executes requests via `AiohttpLoadClient`.
  4. `load_engine.py` uses `AiohttpLoadClient` when `engine_module.target_client` is NOT monkeypatched, while keeping `httpx.AsyncClient` compatibility seamlessly when tests monkeypatch `target_client` or pass an `httpx.AsyncClient` directly into `_read_response()`.
  5. All SSRF/DNS/redirect invariants (`test_outbound_target_policy.py`, `test_target_privacy.py`), existing 204 tests, and a before-vs-after `aiohttp+winloop` benchmark pass cleanly.

---

## 2. Affected Files
- `[MODIFY]` `pyproject.toml` — align `requires-python = ">=3.12,<3.14"`, add `aiohttp` and platform-specific `winloop`/`uvloop`.
- `[NEW]` `backend/core/http_runner.py` — `SSRFPinnedResolver`, `_SSRFCheckedTCPConnector`, `AiohttpLoadClient` (`stream_request()` returning status, bytes_discarded, preview, timed_out, error_kind, headers).
- `[MODIFY]` `backend/core/worker_process.py` — use `winloop`/`uvloop` loop factory in `run_worker_process` and `AiohttpLoadClient` inside `_ProcessWorkerRunner`.
- `[MODIFY]` `backend/core/load_engine.py` — use `AiohttpLoadClient` for live un-mocked runs while preserving `httpx` fallback for mocked `target_client` and direct `_read_response(httpx_client, ...)` calls.
- `[NEW]` `supporting files/testing/unit/test_aiohttp_runner.py` — unit & SSRF tests for `SSRFPinnedResolver`, bare-IP bypass rejection, redirect refusal (`302`), 4 KB streaming + 10 MB infinite-stream cap, and `winloop` worker loop execution.
- `[NEW]` `supporting files/testing/verification/bench_scale02_aiohttp.py` — multi-process `aiohttp + winloop` benchmark vs `SCALE-01` (`httpx` baseline `806.1 RPS`).

---

## 3. Detailed Execution Prompt (Issue 2 — `SCALE-02`)

> **Task:** Execute `SCALE-02` by creating `backend/core/http_runner.py` (`aiohttp` + `SSRFPinnedResolver`), enabling `winloop`/`uvloop` inside `worker_process.py`, and wiring `AiohttpLoadClient` into hot-path execution in `worker_process.py` and `load_engine.py` without breaking any `httpx`/`MockTransport` tests.
>
> **Exact Steps to Execute:**
> 1. **Update `pyproject.toml`:** Update `requires-python = ">=3.12,<3.14"` and add `"aiohttp>=3.13,<4"`, `"winloop>=0.8; sys_platform == 'win32'"`, `"uvloop>=0.21; sys_platform != 'win32'"`.
> 2. **Create `backend/core/http_runner.py`:**
>    - Implement `install_fast_event_loop_factory()` returning `winloop.new_event_loop` on `win32` (or `uvloop.new_event_loop` on POSIX) with safe `None` fallback.
>    - Implement `SSRFPinnedResolver(aiohttp.abc.AbstractResolver)`: cache validated IP addresses for `dns_cache_ttl=60.0`s per `(host, port)` via single-flight `asyncio.Lock`, resolve using `target_policy.resolve_addresses(host, port, is_sandbox)`, convert `DestinationTimeoutError` to `TimeoutError`, and validate literal IPv4/IPv6 addresses cleanly too (so IP literals never bypass `is_sandbox` rules).
>    - Implement `_SSRFCheckedTCPConnector(aiohttp.TCPConnector)`: override `_resolve_host` so even literal IP hosts are verified against SSRF rules before socket connect, keeping `ssl=ssl_context`, `limit=connections`, `limit_per_host=connections`, `ttl_dns_cache=60`, `keepalive_timeout=30`, `enable_cleanup_closed=True`.
>    - Implement `AiohttpLoadClient`: validate URL against `self.base` & `is_sandbox` (`_fast_validate` + `bound_target` fallback), force pinned `Host` header, issue `session.request(method, url, headers=req_headers, data=content, allow_redirects=False, timeout=ClientTimeout(total=remaining))`, iterate `resp.content.iter_chunked(CHUNK_SIZE_BYTES)` up to `MAX_RESPONSE_BYTES` (`10 * 1024 * 1024`), capture first chunk when `capture or status == 403`, call circuit breaker observers cleanly after body stream completes, and close session cleanly in `__aexit__`.
> 3. **Update `worker_process.py` & `load_engine.py`:**
>    - In `worker_process.py`: launch `asyncio.run(runner.run(), loop_factory=fast_loop_factory)` and execute hot-path requests through `AiohttpLoadClient`!
>    - In `load_engine.py`: when `_DEFAULT_TARGET_CLIENT` is NOT monkeypatched (`target_client is _DEFAULT_TARGET_CLIENT`), run in-process hot-path via `AiohttpLoadClient`; otherwise preserve the exact `httpx` client path (`target_client(...)` + `_read_response(httpx_client, ...)`). Keep `engine._read_response` working on `httpx.AsyncClient` instances passed directly by unit tests (`test_automatic_brakes.py`).
> 4. **Write Tests & Benchmark:**
>    - Add `supporting files/testing/unit/test_aiohttp_runner.py` testing: SSRF literal loopback/private block, DNS rebinding rejection, non-redirect on `302`, 4 KB chunked read + 10 MB oversized stream abort, and live `AiohttpLoadClient` requests against a local loopback server.
>    - Add `supporting files/testing/verification/bench_scale02_aiohttp.py` comparing multi-process `aiohttp + winloop` (`64` VUs, `3s`) against the `SCALE-01` `httpx` baseline (`806.1 RPS`).
> 5. **Verify Gate:** Run `py -m pytest "supporting files/testing/unit/test_aiohttp_runner.py" "supporting files/testing/unit/test_outbound_target_policy.py" "supporting files/testing/unit/test_multiprocess_engine.py" -v`, full `py -m pytest "supporting files/testing/unit" -q --tb=short`, `check_local_sandbox.py`, and `bench_scale02_aiohttp.py`, then record `SCALE-02 - aiohttp and winloop Engine.md`.
