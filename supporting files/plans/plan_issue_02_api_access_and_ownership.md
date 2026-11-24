# Issue 02 — API access and ownership

- Introduce a request-scoped operator identity. Shared routes require a verified Supabase access token. An explicit offline setting grants a separate local identity only for loopback requests with local host and origin checks. Its identity cannot reach legacy or Supabase records.
- Derive all owner keys from the operator identity. Scope profile, traffic preferences, targets, journeys, history, and reports. Preserve unowned legacy rows under their existing keys and exclude them from user-facing queries. Do not assign legacy rows by email or editable metadata.
- Keep one shared engine slot. Capture the owner at start, enforce ownership on stop and fault simulation, and deliver telemetry only to the run owner. Require WebSocket authentication in the first frame before delivering any data and close sessions at token expiry.
- Wire the frontend dashboard requests and export to the existing Supabase access token. Keep shared provider sign-in for issue 03. Test missing or expired auth, isolation between two verified accounts, legacy data retention, and the explicit offline boundary with scratch SQLite and mocked authentication.
