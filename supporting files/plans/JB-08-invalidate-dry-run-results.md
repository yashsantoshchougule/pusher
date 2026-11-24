# JB-08 — An old green result can stay on screen

Should Fix · [API Journey Builder issue index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit?usp=drivesdk)

## Implementation prompt

Show a green dry-run result only for the draft and target it actually tested. The audit reproduced a surviving PASS after editing and a rejected new request.

1. Clear live results and their message on draft edits, target or Guard changes, cache option changes, and new attempts. Track a revision so a late result cannot restore a stale card.
2. Ignore repeated dry-run submissions during an active request. Keep the authenticated API response handling and treat server-stored step history as historical.
3. Test a failed retry after success and a result arriving after a draft edit. Run builder, target and dry-run view regressions.

## Verification

16 Node tests passed across the builder, dry-run result and target fixtures. [Drive report](https://docs.google.com/document/d/1LqJGtxy_sFWewNjR9Es060T6F8uixKMQ0fGM0mxnCF0/edit?usp=drivesdk)
