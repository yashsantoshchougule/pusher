# R02 Missing token extraction can still pass

Must Fix. [Pusher Recheck — Issue Index](https://docs.google.com/document/d/1ly_V4x7fTuRIa0-n818n-kPzQIt5Qcmrf8MFCynCq6o/edit)

Both journey executors can accept a successful HTTP status even when a required response field is missing. The worker also retains a prior cycle's context. In both cases downstream steps can send the wrong value or an unresolved placeholder.

1. Share request interpolation and response extraction between the dry run and the load worker. Accept nonempty scalar fields in the existing 4 KiB JSON preview and return a clear error for missing, malformed, or unusable values. Resolve path, header, and body variables before any network I/O.
2. Stop the dry run at the first error. For scheduled runs, reset context each journey cycle, record a failed extraction against its step, and finalize with a failed verdict. Preserve the existing status handling and destination checks.
3. Add mocked cases under supporting files/testing/unit for malformed and empty extraction, legitimate zero and false values, unresolved variables, and an extraction failure after a successful cycle. Run pytest on the new cases, journey validation, Stage 4, and sandbox formats with isolated SQLite.

Existing valid templates and the sandbox token chain retain the same wire format. No migration is needed.
