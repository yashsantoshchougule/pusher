# R03 The dashboard’s sandbox preset fails

Must Fix. [Pusher Recheck — Issue Index](https://docs.google.com/document/d/1ly_V4x7fTuRIa0-n818n-kPzQIt5Qcmrf8MFCynCq6o/edit)

The reset button embeds a different login route and response key than the built-in sandbox. The first step is rejected and subsequent steps cannot obtain a token.

1. Serve the existing sandbox steps from an operator-protected endpoint in local development. Integrate the dashboard reset with that endpoint. Keep the current editor values when fetching the preset fails.
2. Verify the preset is gated by operator access and disabled in shared mode. Update the sandbox integration test and loopback smoke script to fetch the same preset as the dashboard and use it for save, dry run, scheduled run and report export.
3. Run pytest on the sandbox and journey tests, and run `uv run --locked python 'supporting files/testing/verification/check_local_sandbox.py'` against a disposable loopback backend.

Existing journeys are left in place until the operator chooses to reset them.
