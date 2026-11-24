# F02 Invalid journeys can produce a false pass

The save, dry-run, and start routes already share step validation. Extend it to check the request shape, header syntax, and unique step IDs before storage or execution. Preserve optional step metadata, JSON request bodies, and common HTTP methods. Return only the step number and invalid field on validation errors.

Observe unexpected worker failures as they occur and use the run cancellation path. Record a failed verdict for worker failures and for ordinary completions with zero recorded requests. Preserve manual-stop and circuit-breaker verdicts. Make the new failed verdict available in history filters.

Use an isolated database and an in-process API client to verify malformed steps return HTTP 422 on save, dry run, and start. Assert no worker starts. Use fake transports to verify worker exceptions and zero-request completions produce failed reports. Run the existing journey, sandbox, and report tests.
