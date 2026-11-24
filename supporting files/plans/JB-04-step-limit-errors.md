# JB-04 — Adding too many steps can crash the page

Must Fix · [API Journey Builder issue index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit?usp=drivesdk)

## Implementation prompt

Enforce the ten-step limit in API Journey Builder and show validation errors without breaking React. The audit verified that an eleven-step save returns a structured HTTP 422 list. Rendering those objects in the banner throws.

1. Set one frontend maximum used by both Add Step and its handler, including repeated clicks. Show the count and disable Add at the cap. Treat existing server validation as authoritative.
2. Normalize both save and dry-run errors. Preserve recognizable plain messages and show a short safe message for structured errors without displaying raw inputs.
3. Test repeated add from nine steps, a structured 422 from both paths, and actual banner rendering. Run the builder view and backend validation checks.

## Verification

5 Node builder and dry-run view tests and 6 backend journey validation tests passed. [Drive report](https://docs.google.com/document/d/1cRSxITHOjvttgaCpiHk2E3Hdv5jpLhgWH1ud68tPpNw/edit?usp=drivesdk)
