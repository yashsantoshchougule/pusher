# RL-04 — Measure real capacity

Deployment Verification, source item 4. [Release readiness index](https://docs.google.com/document/d/1VbRL-9GJ90Pq6VpJdidtVzftJS3Ad7kd5cq9OaIYt9g/edit)

PA-11 recorded short, single-process observations at 1, 5, and 10 virtual users. Add an explicit `--benchmark` option alongside the existing smoke check and `--measure` option.

1. Start an isolated runner and separate target on ephemeral loopback ports, with temporary SQLite files. Allow only that target origin and verify it using the normal sandbox route.
2. Check the published worker and RAM bounds. Run three sequential 15-second observation windows each at 10, 25, and 50 VUs. Set a 20-second engine deadline and request normal Stop at the end of each window. Keep existing automatic brakes and the 500 MB budget. Report early stops and skipped levels.
3. Sample each process's CPU and RSS, target-side established TCP connections, and actual active users. Capture Stop time and finalized report throughput, latency, error rate, and verdict. Record connection readings as unavailable if the host denies access.
4. Save the measured outcomes and reproduce them via `check_local_sandbox.py --benchmark`. This bounded fixture establishes local measurements. Representative staging measurements require an authorized target, the intended runner and target hardware, a confirmed traffic budget, and agreed latency and error targets.
