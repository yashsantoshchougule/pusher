# PA-02 — Preserve omitted profile fields

Priority: Must Fix

Master: https://docs.google.com/document/d/1J9sPxjf_nf7PTuI4aV27e3jL_5rZ59tQ5bM4b3ZOEAs/edit?usp=drivesdk

## Task prompt

Fix partial updates through PUT /api/profile so changing one field retains all other stored values. Allow explicit empty text to clear a field. Continue taking the account key and email from the verified session and keep existing RAM validation and SQLite schema.

## Verified baseline and scope

profile_router.py already discards omitted and null fields. profile_service.py sanitizes every known field into a full map, so merging that map overwrites unrelated stored values with blanks and 500 MB. Add the regression to supporting files/testing/unit/test_profile_backend.py against the API and scratch SQLite. Keep owner enforcement, sanitizer bounds, and database schema intact.

## Implementation and checks

1. Save a profile with populated fields and 750 MB. Update only the name and explicitly clear a separate field. Confirm the original implementation loses organization and RAM.
2. Overlay only explicitly submitted sanitized fields and retain the existing email fallback for identities without an email.
3. Verify PUT and subsequent GET both retain omitted values, preserve account ownership, and persist an explicit empty string.
4. Run `python -B -m pytest -q -p no:cacheprovider 'supporting files/testing/unit/test_profile_backend.py' 'supporting files/testing/unit/test_operator_access.py'` with the pinned interpreter. Revert the service and test changes to back out. No migration is required.

