# JB-02 — Expected Status can accept the wrong response

Must Fix · [API Journey Builder issue index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit?usp=drivesdk)

## Implementation prompt

Enforce the status selected in the editor exactly. Both executors currently treat 201 as a match for 200, which hid a misconfigured sandbox checkout preset.

1. Require equality in the dry-run service and scheduled journey worker. Keep handling transport failure, extraction, and explicitly chosen non-2xx codes.
2. Set the built-in checkout preset and corresponding integration fixture to 201, its real response. Keep user-saved assertions intact. An old sandbox journey expecting 200 should be updated to 201 or reset.
3. Test 201/200 mismatches in both paths, a matching 201, deliberate non-2xx assertions, and the full sandbox flow. Run the verdict, extraction, Stage 4, and sandbox format tests.

## Verification

All 36 focused backend tests passed and the loopback sandbox check passed. A 201 fails a step expecting 200 and passes a step expecting 201. Older saved sandbox checkout steps should expect 201. [Previously verified Drive report](https://docs.google.com/document/d/1_R_808OwiJVmCp8y4C94-d1Hjbo8xrHx5Iu4aR9aRbQ/edit)
