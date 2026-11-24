# F01 - Active runs continue after Guard expiry

Must Fix. [Master report](https://docs.google.com/document/d/1Xz_RH_8rup4vp8Kj0muVhWORa7PfliAsbpMMTZDKgOw/edit?usp=drivesdk)

The load start route checks the verified Guard, but the engine only knows the requested duration. The final verification observed requests continuing after expiration.

1. Pass the verified Guard's expiry timestamp into the engine as a fixed deadline for that run.
2. Check the deadline in the scheduler and shared HTTP send path. Cap request time including body streaming by the remaining verification time. Use the existing stop lifecycle and record an expiry verdict.
3. Verify that a one-user test with a short sandbox Guard stops before its configured duration, opens no new requests after expiry, and finalizes its report. Exercise in-flight cancellation through a mocked transport.

No database migration is required. Rollback is limited to the new deadline argument, checks, and regressions. Run `uv run --locked python -m pytest "supporting files/testing/unit/test_guard_deadline.py" "supporting files/testing/unit/test_emergency_stop.py"`.
