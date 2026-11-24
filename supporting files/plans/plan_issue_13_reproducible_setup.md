# Issue 13 — Reproducible setup

- Declare Python 3.12.14, lock runtime and test dependency groups with uv, and document local and shared configuration. Keep service credentials out of editions and fixtures.
- Supply synthetic auth credentials and local transports for tests. Update older tests to use scoped sessions, authorized mock targets, the new shutdown contract, and paginated history. Keep negative access tests exercising the real verifier.
- Verify the locked setup in a clean project copy without .env, run the full Python and Node suites, build the frontend, and exercise the offline sandbox from target verification through report export.
