# JB-03 — A slow save can erase newer edits

Must Fix · [API Journey Builder issue index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit?usp=drivesdk)

## Implementation prompt

Preserve the latest local journey when a save response arrives late. Reproduction: submit a draft, edit a step before the response, then observe the response replace the edited step with the submitted value.

1. Track changes to both the step list and run mode since submission. Use the server's normalized metadata and tab-only inputs when the acknowledged draft still matches. If the draft changed, keep the current edits and explain that an earlier snapshot was saved.
2. Prevent concurrent save actions and stop Save & Launch when the user changed the draft during save. Keep the existing rule that an API rejection never starts a run.
3. Add dashboard tests with a deferred response for later edits, duplicate actions and stale launch. Use the existing mocked fixture and run the focused Journey Builder, journey launch and Traffic Setup tests.

## Verification

15 Node tests passed across test_journey_builder.mjs, test_journey_launch.mjs and test_traffic_dashboard.mjs. The regression held a save open while editing. [Drive report](https://docs.google.com/document/d/1PQfJ3EpU5zwFQ_Tjf2VjcVLpIIWyGKLMPVWlTqgTNLE/edit?usp=drivesdk)
