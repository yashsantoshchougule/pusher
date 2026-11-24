# PA-11 — Verify host capacity and resource claims

Priority: Deployment Verification

Master: https://docs.google.com/document/d/1J9sPxjf_nf7PTuI4aV27e3jL_5rZ59tQ5bM4b3ZOEAs/edit?usp=drivesdk

## Task prompt

Produce a bounded, reproducible measurement of the local engine using only the built-in loopback target and disposable storage. Measure observed users, throughput, peak sampled RSS, concurrent TCP connections, and Stop latency. Preserve all scheduler, memory, socket and destination safety limits. Document what the results do and do not establish.

## Verified baseline

system_router.py and load_router.py expose configured RAM and worker limits. load_engine.py enforces them and records measured metrics. No representative benchmark fixture exists. check_local_sandbox.py already starts a disposable loopback backend and exercises one complete run. Reuse that setup.

## Execution and acceptance

1. Add an opt-in measurement to the existing verification script. Exercise 1, 5, and 10 steady virtual users for about 2.5 seconds each. Use the existing verified local target without extra traffic features. Sample RSS for the combined runner/sandbox process and count the sandbox listener's open TCP connections, including the control client. Direct socket enumeration failed in the Windows sandbox, so count Uvicorn's actual open connections locally.
2. Time the normal owner-authorized Stop call and verify the stopped snapshot, matching report ID and peak VUs. Record throughput and raw counters. Keep the normal smoke run unchanged when the option is absent.
3. Run `python -B 'supporting files/testing/verification/check_local_sandbox.py' --measure` using the locked interpreter plus the existing Stop and lifecycle tests. This only establishes a healthy low-load measurement on this machine.
4. Release-scale acceptance requires representative hardware, an agreed test budget and authorized staging configured with realistic target behavior. Record repeat runs and measurement conditions before making capacity or Stop-time claims. No runtime capacity change is in scope.

## Local result

| Observed VUs | Combined peak sampled RSS (MiB) | Peak sandbox TCP connections | Report peak RPS | Requests | Stop HTTP (ms) |
| --- | --- | --- | --- | --- | --- |
| 1 | 73.4 | 2 | 93 | 218 | 34.2 |
| 5 | 75.2 | 6 | 91 | 235 | 68.5 |
| 10 | 77.0 | 11 | 57 | 179 | 137.0 |

One short Windows loopback sample at each level. The same Python process ran the engine and target. The connection count includes the control client. All three Stop requests confirmed drained runs and produced matching MANUAL_ABORT exports. The eight focused Stop and load-engine unit tests passed. Keep release-scale capacity open pending representative measurements.

