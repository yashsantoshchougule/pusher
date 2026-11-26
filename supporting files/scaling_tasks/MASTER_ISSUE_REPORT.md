# Master Issue Report: Pusher Scalability & Hardening (`SCALE-01` – `SCALE-06`)

**Storage Mode:** Local-only under `supporting files/scaling_tasks/` (no GitHub / Drive sync).
**Approved Master Plan:** `implementation_plan_scaling_architecture.md`
**Baseline Environment:** Windows 11, Python `3.13.15` (AMD64), `200 passed` unit tests, `98` `.mjs` + `10` `.cjs` Node tests passing, single-process Uvicorn + `httpx`/`httpcore` + sync `sqlite3`.

---

## Issue Register (Strict Gated Sequence)

| Order | ID | Priority | Exact Issue Title | Status | Saved Plan & Prompt | Verified Report |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `SCALE-01` | Must Fix | Multi-Process Worker Pool & Production Entrypoint Separation | `Resolved locally` | [Plan](plans/SCALE-01-multi-process-worker-pool.md) | [Report](reports/SCALE-01%20-%20Multi-Process%20Worker%20Pool.md) |
| 2 | `SCALE-02` | Must Fix | Switch Hot-Path HTTP Engine from httpx/httpcore to aiohttp + winloop/uvloop | `Resolved locally` | [Plan](plans/SCALE-02-aiohttp-winloop-transport.md) | [Report](reports/SCALE-02%20-%20aiohttp%20and%20winloop%20Engine.md) |
| 3 | `SCALE-03` | Must Fix | Eliminate Idle Worker Polling & O(N log N) Per-Tick Latency Sorting | `Resolved locally` | [Plan](plans/SCALE-03-zero-poll-and-o1-buckets.md) | [Report](reports/SCALE-03%20-%20Zero-Poll%20and%20O1%20Buckets.md) |
| 4 | `SCALE-04` | Must Fix | Support Multiple Concurrent Runs (RunManager instead of Global LoadEngine Singleton) | `Resolved locally` | [Plan](plans/SCALE-04-concurrent-run-manager.md) | [Report](reports/SCALE-04%20-%20Concurrent%20RunManager.md) |
| 5 | `SCALE-05` | Should Fix | Non-Blocking Database I/O & Async Write Offload | `Resolved locally` | [Plan](plans/SCALE-05-non-blocking-db-io.md) | [Report](reports/SCALE-05%20-%20Non-Blocking%20DB%20IO.md) |
| 6 | `SCALE-06` | Should Fix | Pre-Allocate Static Headers, Parsed URLs & Cache-Buster Fast Path | `Resolved locally` | [Plan](plans/SCALE-06-preallocate-hotpath-templates.md) | [Report](reports/SCALE-06%20-%20Hot-Path%20Pre-Allocation.md) |

The statuses above reflect the saved local reports. See [the current app integration check](../plans/RL-06-combined-ui-backend-check.md) for the updated browser and regression evidence. Release publication and representative staging measurements are separate.

---

## Gate Rules
1. Process **one issue at a time** in strict order (`SCALE-01` → `SCALE-06`).
2. Before modifying code for Issue $k$, save its full analysis and **Detailed Execution Prompt** in `supporting files/scaling_tasks/plans/`.
3. After implementation, verify with unit tests, security/contract invariants, and benchmarks, then write the verified report in `supporting files/scaling_tasks/reports/`.
4. Advance to Issue $k+1$ **only after Issue $k$ passes verification**.
