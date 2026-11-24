# VT-02 — Kill ID can look successful when the connection fails

Must Fix, second finding in the [Verify Target issue index](https://docs.google.com/document/d/1XKs8rqWzChBeCU9trm5WjBJDnI2h8Hj29FfzIDciZI0/edit).

## Implementation prompt

Make Kill ID reflect the existing authenticated endpoint's result. The dashboard's catch branch currently clears the Guard and marks it manually revoked if the response is lost or unreadable. A rejected HTTP response can also hide a real revocation until a reload. The review reproduced the false success with a mocked network error.

1. Start with a cleared error. Use the server's revocation fields for a confirmed success. Preserve the user's last confirmed state when the outcome is unknown and show a clear error.
2. Refresh authoritative status after success, an HTTP rejection or a connection failure. If the server cannot confirm the change, leave the Guard and Kill ID available for retry.
3. Test the Dashboard handler with mocked HTTP and a synthetic Guard. Cover an unreachable server and successful retry, an unreadable reply, and a rejected request where a subsequent status response confirms revocation.
4. Run `node --test "supporting files/testing/unit/test_verify_target_dashboard.mjs"` and the frontend production build.

Keep the kill endpoint and device binding contract intact. A rollback consists of the local handler and its focused test changes.

## Verification

All three mocked scenarios failed before the fix and passed afterward. The frontend production build passed. [Drive resolution](https://docs.google.com/document/d/1AI4KdsyKzXzBDU2VNfIHIGoF6qZLZnp4g3QxXwpuYWs/edit)

```powershell
node --test 'supporting files/testing/unit/test_verify_target_dashboard.mjs'
```
