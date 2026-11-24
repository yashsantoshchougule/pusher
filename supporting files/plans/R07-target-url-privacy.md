# R07 The main target URL can still save private values

Must Fix. [Pusher Remediation — Remaining Issues](https://docs.google.com/document/d/1RpVDZM22lKwMj5eGugDi6j5t_-obO1TfsMldBH5kJQI/edit)

The current Guard store and report writer copy the entire URL. SQLite and responses can retain session tokens or other private query values. The ownership challenge already uses a separate fixed route and the Guard artifact only contains the target origin.

1. In the active target SQLite schema, store the query-free URL and a boolean requirement. Infer the requirement when reading an older row. Normalize the submitted URL at issuance and successful verification. Preserve scheme, host, port, path, and existing Guard checks.
2. At the load start endpoint require the runtime query for single-target runs when recorded by verification. Pass it to the existing checked transport in memory. Journey steps continue using their own URLs. Allow explicit successful query-free verification to clear the requirement.
3. In the dashboard keep the current input across status refreshes only for the same Guard and endpoint. Show the query requirement when reopening. Redact summary displays, DNS response echoes, WAF diagnostic fields, and report persistence, reads, exports, and search. Extend the existing opt-in offline SQLite scrub to legacy target and report URLs.
4. Run pytest against the target privacy, Stage 1, outbound policy, report, and database tests in a scratch database with HTTP mocks. Add Node coverage for status refresh and Guard replacement. Verify that the query reaches only the mock transport, reports and scratch SQLite exclude it, and old rows keep their runtime requirement after offline cleanup.

Existing targets use the same Guard and origin. Re-enter the query after reopening or explicitly verify a query-free URL to clear the requirement. Run legacy cleanup only after stopping Pusher and preparing a protected recovery copy. Rolling back code does not recover query values deleted by maintenance.
