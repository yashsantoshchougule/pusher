# VT-01 — A revoked Guard can still show Verified

Must Fix, first finding in the [Verify Target issue index](https://docs.google.com/document/d/1XKs8rqWzChBeCU9trm5WjBJDnI2h8Hj29FfzIDciZI0/edit).

## Implementation prompt

Correct the status reported by the authenticated `GET /api/target/status` route. Treat the persisted revocation record as authoritative when its Guard ID still appears in the saved target. Report that Guard as revoked, unverified and inactive, with zero seconds. Retain the ID and the stored revocation reason so the existing banner can explain what happened.

The review seeded a disposable SQLite database with an active verified Guard and its revocation record. Status returned verified and revoked with 600 seconds left. `backend/api/target_router.py` already reads the record but uses the cached target fields when it reports verification. Dashboard and WAF read this response. Outbound enforcement already rejects revoked IDs.

1. Read the revocation record before checking the clock. Skip expiry processing for an already revoked ID and preserve its reason.
2. If the clock check records a new expiry, read that record for the response. Preserve pending Guards, valid timers, the legacy replacement requirement and the semantics of explicit manual revocation.
3. Add an isolated status regression to `supporting files/testing/unit/test_stage1_backend.py`. Exercise the API with a synthetic sandbox Guard and a revocation record. Assert the change from verified to revoked and check that the status and reason stay revoked even if the original deadline has passed.
4. Run the new node and the existing Stage 1, outbound policy, edge diagnostics and Guard deadline tests with the pinned project environment. Keep the database temporary and traffic mocked or in-process.

The response keys stay compatible. The fix needs no schema migration. Roll back the scoped status and regression changes together if the API contract fails.

## Verification

The new status regression failed before the fix and passed afterward. The related backend run passed all 43 tests. [Drive resolution](https://docs.google.com/document/d/18QWr042L4JZQNKnfaj45URf9aSh5wvja3Ph-vdM0Bhs/edit)

```powershell
python -B -m pytest -q -p no:cacheprovider 'supporting files/testing/unit/test_stage1_backend.py' 'supporting files/testing/unit/test_outbound_target_policy.py' 'supporting files/testing/unit/test_edge_diagnostics.py' 'supporting files/testing/unit/test_guard_deadline.py'
```
