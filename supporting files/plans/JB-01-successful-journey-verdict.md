# JB-01 — A broken journey can get a PASS

Must Fix · [API Journey Builder issue index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit?usp=drivesdk)

## Implementation prompt

Fix the authoritative verdict for scheduled API journeys. The audit ran a mocked two-step chain: the first step returned 200, the second always returned 404, and the engine saved PASSED even with zero completed chains. A normal timed-out-at-duration run may pass only when a worker has successfully executed every step of at least one chain.

1. Trace where per-request accounting ends in the journey worker and how finalization persists and exports the verdict. Add a per-run completed-journey counter that resets at start and increments only after the final step, including extraction, succeeds. Interrupted or failed chains must never increment it.
2. Apply the counter specifically to finished journey runs. Leave request-based success, manual abort, cancellation, circuit breakers, and explicit failure precedence intact. Preserve the report schema and existing reports.
3. Extend test_run_verdict.py with mock HTTP journeys for persistent failure, a full success between failures, and partial completion at the deadline. Check persisted and exported verdicts and the single-target and abort regressions.
4. Run the focused cases against the baseline and after the change, then run journey and load lifecycle regression tests. Use only synthetic transports and temporary databases.

## Verification

The regression reproduced the false PASS before the fix. Afterward, the verdict module passed 11 tests, including the deadline case. The earlier focused run passed 29 tests covering the verdict, extraction, Stage 4, and emergency stop. The stored and exported verdict both follow the new rule. [Previously verified Drive report](https://docs.google.com/document/d/1Nns5tYHKjCHU91TInC0uvQhsJQRKVcBmxIFr1F2clCE/edit)
