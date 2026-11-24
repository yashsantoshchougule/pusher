# Issue 06 — Report loss

- Generate new run IDs with UUIDs while keeping all existing IDs addressable. Remove startup deletion by hardcoded ID.
- Make storage of the same completed run idempotent. A duplicate write must retain the original report and must never replace another operator's report.
- Exercise distinct run IDs, duplicate writes, and reinitialization of a legacy SQLite schema in the isolated test database.
