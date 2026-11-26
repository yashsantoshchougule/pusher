# SCALE-02 - Switch Hot-Path HTTP Engine from httpx/httpcore to aiohttp + winloop/uvloop

**Master Tracker:** [MASTER_ISSUE_REPORT.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/MASTER_ISSUE_REPORT.md)
**Saved Plan & Prompt:** [SCALE-02-aiohttp-winloop-transport.md](file:///c:/yash/projects/pusher/supporting%20files/scaling_tasks/plans/SCALE-02-aiohttp-winloop-transport.md)

---

## Issue
- **ID & Priority:** `SCALE-02` — `Must Fix`
- **Symptom & Impact:** Pure-Python `httpx` + `httpcore` pooling/parsing and `ProactorEventLoop` scheduling limited single-process concurrency (`206.1 RPS`, `474 ms` p95 at 64 VUs) and added per-request wrapper allocations.

## How It Occurred
`worker_process.py` and `load_engine.py` executed hot-path requests through `httpx.AsyncClient` and `httpcore.AsyncConnectionPool` rather than Cython `aiohttp` (`llhttp`) + `winloop`/`uvloop`.

## How It Was Solved
- **[MODIFY] [pyproject.toml](file:///c:/yash/projects/pusher/pyproject.toml)**: Expanded `requires-python` to `">=3.12,<3.14"` and added `aiohttp>=3.13,<4`, `winloop>=0.8; sys_platform == 'win32'`, and `uvloop>=0.21; sys_platform != 'win32'`. Installed `aiohttp 3.14.5` & `winloop 0.8.4`.
- **[NEW] [http_runner.py](file:///c:/yash/projects/pusher/backend/core/http_runner.py)**: Added `AiohttpLoadClient`, `SSRFPinnedResolver(AbstractResolver)` (DNS resolution pinning + optional 60s TTL cache), `_SSRFCheckedTCPConnector` (closing literal-IP resolver bypass), `allow_redirects=False`, pinned `Host` header, 4 KB chunk discard, 10 MB infinite-stream abort cap (`MAX_RESPONSE_BYTES`), and `get_fast_loop_factory()`.
- **[MODIFY] [worker_process.py](file:///c:/yash/projects/pusher/backend/core/worker_process.py)** & **[load_engine.py](file:///c:/yash/projects/pusher/backend/core/load_engine.py)**: Switched worker processes to `winloop` (`asyncio.run(..., loop_factory=...)`) + `AiohttpLoadClient`, and switched un-mocked in-process runs to `AiohttpLoadClient` while preserving full `httpx`/`MockTransport` unit-test compatibility.

## Testing
- **Targeted Tests (`test_aiohttp_runner.py`, `test_outbound_target_policy.py`, `test_multiprocess_engine.py`):** `17 passed in 14.72s` (exit `0`, zero warnings).
- **Full Python Suite:** `py -m pytest "supporting files/testing/unit" -q --tb=short`: **`208 passed, 30 warnings in 30.52s`** (exit `0`).
- **Sandbox Check:** `py "supporting files/testing/verification/check_local_sandbox.py"` — passed (exit `0`).
- **Benchmark (`bench_scale02_aiohttp.py`, 64 VUs, 3s):**
  - `aiohttp_single` (`1` process): **`6,402` requests (`2,117.3 RPS`, `p95_ms = 22 ms`)** — **10.3x RPS / 21.5x lower p95** vs `SCALE-01` `single_process` `httpx` (`206.1 RPS`, `474 ms`).
  - `aiohttp_winloop_mp`: **`3,082` requests (`718.4 RPS` wall incl. spawn, `p95_ms = 7 ms`)**. Notice 64 VUs is fast enough in 1 `aiohttp` process that spawn overhead exceeds single-process time below ~128 VUs; `SCALE-03` will tune the threshold & shrink IPC payload size.

## Result
- **Status:** `Resolved`
- Passed all `SCALE-02` acceptance gates; cleared to advance to `SCALE-03`.
