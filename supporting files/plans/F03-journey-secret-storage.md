# F03 Saved journeys store secrets in plaintext

Keep step metadata and reusable header templates in SQLite. Only persist the recognized content types and complete extracted-variable references. Keep every request body and other header values in browser or request memory. Return the persisted step order and safe fields on save, and merge the submitted runtime inputs back into the current tab. Require operators to supply missing inputs before dry run or launch. Show the requirement beside the input.

Treat older rows as templates when read. Supply an explicit maintenance command to remove their raw inputs and compact SQLite while the backend is stopped. Preserve step identifiers, owners, order, and non-sensitive metadata. Remove persisted dry-run error text, which may contain runtime header values. Exercise the migration on a scratch database. Running the scrub on an existing user database requires an explicit maintenance action.

Test a save containing synthetic bearer, custom-header, and body values. Check API responses, SQLite contents, dry run and start with and without runtime inputs, and save-and-launch merging. Seed legacy rows and verify the scrub preserves the structure while removing raw values from the scratch database and WAL. Keep malformed legacy headers blocked pending an explicit edit.
