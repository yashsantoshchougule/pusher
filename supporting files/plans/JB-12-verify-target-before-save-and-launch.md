# JB-12 — Check target verification before Save & Launch

Must Fix. First finding in the API Builder follow-up review. The [Journey Builder audit index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit) tracks the preceding issues. Drive access to that folder is currently unavailable, so this follow-up uses the chat finding as its source.

## Implementation prompt

An unverified target currently leaves Save & Launch available. The dashboard sends a save request with journey mode enabled before the shared launch handler discovers the missing verification. Checking verification before saving prevents both an unintended mode change and an unnecessary detour to Verify Target.

1. Reuse the dashboard's verified-target status and current run state for a common launch blocker. Preserve the Traffic Setup checks and the backend's final verification.
2. Pass the blocker to API Builder. Render it next to Save & Launch, disable the button, and check the same blocker before the handler calls the save API. Keep Save Journey Configuration available for drafts.
3. In the existing dashboard fixture, reproduce the unintended save with an unverified target. Verify that Save & Launch sends neither request, while Save alone still works and a verified Save & Launch sends the acknowledged journey.
4. Run `node --test 'supporting files/testing/unit/test_journey_builder.mjs' 'supporting files/testing/unit/test_journey_launch.mjs' 'supporting files/testing/unit/test_traffic_dashboard.mjs'`.

The change uses existing API and state contracts. Reverting the scoped dashboard, view, and regression changes restores the previous behavior.

## Resolution

**How it occurred.** Save & Launch checked verification after saving the draft with journey mode enabled.

**How it was solved.** The Builder uses the verification and run-readiness blocker in both the button and the handler. A blocked click leaves the draft unchanged. The separate Save action remains usable.

**Testing.** The new unverified case reproduced the unintended save. The verified control case passed before the fix. After the fix all 28 tests in the focused command passed, including the acknowledged-save launch.

**Result.** Resolved locally. The report was published and verified after access to the original audit folder was restored. [Drive report](https://docs.google.com/document/d/1d8VXH2bqkpuWcJwRuazCWxVMW4uiumaNm2zJi0iDsHc/edit?usp=drivesdk)
