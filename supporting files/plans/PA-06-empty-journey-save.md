# PA-06 — Block saving an empty journey

Priority: Should Fix

Master: https://docs.google.com/document/d/1J9sPxjf_nf7PTuI4aV27e3jL_5rZ59tQ5bM4b3ZOEAs/edit?usp=drivesdk

## Task prompt

Prevent an empty journey from being saved in API Builder. Explain the missing step in the view and skip the save HTTP call even if the handler is invoked directly. Saving a nonempty journey must still work without verified target ownership. Save & Launch and Dry Run keep their current independent gates.

## Verified baseline and scope

ApiBuilderView.jsx disables standalone Save only while saving. DashboardPage.jsx submits journeySteps to /api/journey/save even when empty. journey_router.py correctly rejects an empty save with 422, and the existing frontend error formatter already renders the response safely.

## Implementation and verification

1. Use the dashboard fixture and real builder rendering in test_journey_builder.mjs. Verify the no-write expectation fails before editing.
2. Disable Save when no steps remain and give a short actionable hint. Guard the shared save handler before setting pending state. Keep the backend as the final validator.
3. Verify an initially empty journey makes no outgoing write and adding a step allows saving. The existing builder prevents deleting its last step, so confirm that behavior stays intact. Run `node --test 'supporting files/testing/unit/test_journey_builder.mjs' 'supporting files/testing/unit/test_journey_launch.mjs'` and the final build.
4. Revert the two frontend changes to roll back. No persisted data or backend API changes are needed.

