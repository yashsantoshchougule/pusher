# ISSUE-02 Verified Report — Fix High-VU Burst False Trips

- **Issue ID:** `ISSUE-02`
- **Priority:** Must Fix
- **Result:** `Resolved`
- **Plan Link:** [issue-02-high-vu-connection-burst-prompt.md](./issue-02-high-vu-connection-burst-prompt.md)

## How It Occurred
`CircuitBreakers` applied the `5 consecutive` crash limit to transient `status == 0` socket drops across thousands of simultaneous VUs, while `worker_process._record()` skewed `breaker_samples` (keeping 100% of failures vs. 1/8 of successes) and `Steady Crowd` connected all VUs in ~1ms.

## How It Was Solved
- Updated [circuit_breakers.py](file:///c:/yash/projects/pusher/backend/core/circuit_breakers.py) to track `consecutive_5xx` (5 consecutive HTTP 5xx) separately from `consecutive_conn` (`5` when `target_vus < 64`, scaled `min(40, max(10, target_vus // 40))` at high VUs, still bounded by rolling error ratio).
- Fixed proportional `breaker_samples` sampling (`_d_total <= 48 or (_d_total & 3) == 0`) and added startup wave micro-stagger in [load_engine.py](file:///c:/yash/projects/pusher/backend/core/load_engine.py) & [worker_process.py](file:///c:/yash/projects/pusher/backend/core/worker_process.py).

## Testing Evidence
- `py -m pytest "supporting files/testing/unit/test_automatic_brakes.py" "supporting files/testing/unit/test_remediation_fixes.py" -q` -> **12 passed**.
- Live stress tests: `500 MB / 500 VUs` completed `ARMED (Normal)` (`20,968` reqs, `9` drops tolerated cleanly); `500 MB / 1,500 VUs` completed `ARMED (Normal)` (`28,390` reqs, `peak_vus=1,417`, `299` drops tolerated without premature abort).
