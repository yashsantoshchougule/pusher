# JB-06 — A dry run can pass while the scheduled run fails on the same steps

Must Fix · [API Journey Builder issue index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit?usp=drivesdk)

## Implementation prompt

Make dry runs and scheduled journeys build equivalent requests. The audit showed that the same step passed a dry run and failed a scheduled run because only the scheduled request added a cache-busting parameter.

1. Share the journey request builder for destination checks, rendered path, headers, body and cache-busting. Keep scheduled and dry-run execution lifecycles and response handling intact.
2. Send the current Traffic Setup cache setting from the builder. Calls without a setting use the owner's stored preference. Keep the previous single-target cache behavior.
3. Use mock HTTP in both executors with cache-busting toggled on and off. Compare URL parameters, method, headers and body. Run the relevant journey, load, destination and sandbox checks.

## Verification

46 backend tests passed. The new mock checks compared both executors with the option enabled and disabled. The local sandbox smoke test passed. The controlled-clock fixture now explicitly disables cache-busting to test cancellation alone. [Drive report](https://docs.google.com/document/d/1dUcsIb9YW12gp2fSFw8RzoH6uowjUd9Bo7zBj6dmi00/edit?usp=drivesdk)
