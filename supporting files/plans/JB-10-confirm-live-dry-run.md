# JB-10 — Dry run can sound safer than it is

Should Fix · [API Journey Builder issue index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit?usp=drivesdk)

## Implementation prompt

Clarify that a dry run issues real HTTP requests, and prevent accidental changes to target data. The current action is called Dry Run and does not identify the destination or warn about write methods.

1. Show the verified origin without its query string. Require an actual verified target to start. Make the dry-run label and description clear about execution.
2. Ask for explicit confirmation before a draft containing a write method is sent. Declining must send no request and preserve the draft and last result. Read-only methods proceed normally.
3. Include the displayed Guard ID in the request. Reject a stale Guard selection before opening a transport. Keep backward compatibility for earlier callers that omit it.
4. Add UI tests for safe requests, declined and accepted writes, and unverified targets. Add an API regression for a stale displayed Guard. Keep all tests on mocks or loopback.

## Verification

16 backend tests and 13 Node tests passed, including invalid Guard, unverified target, declined writes, accepted writes and read-only runs. [Drive report](https://docs.google.com/document/d/1HhQhVd8WVU_1c7TRAXgprCntWhiqOfjdSfcu6gUMjoY/edit?usp=drivesdk)
