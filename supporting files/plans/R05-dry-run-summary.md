# R05 The dry-run summary drops valid results

Should Fix. [Pusher Recheck — Issue Index](https://docs.google.com/document/d/1ly_V4x7fTuRIa0-n818n-kPzQIt5Qcmrf8MFCynCq6o/edit)

The API provides `total_duration_ms` and `extracted_context`, while the view reads different keys. The saved dry-run history is a list and can also crash the live results panel on reload.

1. Use the actual duration and extract only variable names for the display. Preserve zero, show a clear empty state, and use the query-free step paths already returned by the API.
2. Render saved step summaries separately from the latest full result. Preserve progress and statuses without claiming saved summaries are full results. Remove the unconditional success message about token chaining.
3. Run node --test on test_dry_run_view.mjs and the final frontend suite. Render current results with and without variables, duration zero, and stored step arrays. Verify the production build and offline sandbox flow.

No API or SQLite migration is needed.
