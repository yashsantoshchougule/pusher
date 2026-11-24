# JB-05 — Values copied between steps can change or break

Must Fix · [API Journey Builder issue index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit?usp=drivesdk)

## Implementation prompt

Preserve values inserted into later journey steps. The audit reproduced invalid JSON for a quoted name and a plus sign decoded as a space in the target query. Both executors share prepare_journey_request.

1. Encode a substituted URL value as a component, without altering the rest of the step URL. Retain the target-origin checks and existing header validation.
2. Substitute within parsed JSON strings, list values and object fields before serialization. Preserve plain text and the exact bytes of JSON text without variables. Keep explicit Content-Type handling and unresolved-variable failure behavior.
3. Keep the body field's text in the editor so a quoted JSON scalar stays quoted. Add tests for nested values, quotes and backslashes, query plus signs, untouched JSON text, and explicit non-JSON bodies.
4. Run extraction, validation, sandbox format and builder tests with mocked transports.

## Verification

34 backend extraction, validation, formats and policy tests and 4 Node builder tests passed. [Drive report](https://docs.google.com/document/d/1HFkCHcllyE8_Z6CTVZuqctldzM-HyxFAdP0X1qnAqEE/edit?usp=drivesdk)
