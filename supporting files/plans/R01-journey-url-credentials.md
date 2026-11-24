# R01 Journey URLs can still store credentials

Must Fix. [Pusher Recheck — Issue Index](https://docs.google.com/document/d/1ly_V4x7fTuRIa0-n818n-kPzQIt5Qcmrf8MFCynCq6o/edit?usp=drivesdk)

The recheck used a disposable database and found a synthetic query credential in the save response and SQLite. Dry-run history and report step metrics also copy the raw step URL. Save the endpoint path and a query-input requirement, and pass query strings directly to the transport in memory. Apply the same rule to all query values so arbitrary credential names are covered.

1. Update the journey SQLite write/read boundaries and saved-step validation. Preserve existing endpoints and the requirement to re-enter a removed query string. Keep the query suffix in the saved journey editor's current tab for Save & Launch, using the returned endpoint path.
2. Remove query strings from dry-run summaries and report step metadata before persistence. Sanitize legacy metadata reads. Extend the documented offline scrub to rewrite legacy journey paths and report step metadata on demand. Verify on scratch SQLite without running the scrub on a user database.
3. Extend the journey privacy Python and Save & Launch Node tests. Prove a synthetic query value reaches the mock transport, never appears in new SQLite data or report/export responses, and is removed from the tested legacy snapshot. Confirm restored queries use the server-acknowledged path and are required after reload. Run `uv run --locked python -m pytest` on the privacy, journey, and report tests and `node --test 'supporting files/testing/unit/test_journey_launch.mjs'`.

After reopening, operators supply saved steps' runtime queries again or clear the requirement. An existing database or backup can retain previously written queries until offline maintenance. Before maintenance, prepare an appropriately protected recovery copy. Roll back application files separately from any operator-run scrub.
