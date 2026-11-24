# Issue 04 — Emergency stop

- Keep the run slot occupied until the orchestrator has canceled the workers, closed the shared client, and finalized the report. Replace the polling delay with an interruptible wait and give each run a fresh stop event.
- Route manual stop, Guard revocation, circuit trips, and simulated spikes through the same shutdown lifecycle. Keep cancellation idempotent and write the report once. Show a failed stop request on the dashboard without clearing the running state.
- Test a deliberately stalled worker and client cleanup, repeated stop calls, restart after cleanup, and report finalization using controlled local I/O.
