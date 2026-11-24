# Issue 11 — Sandbox HTTP formats

- Encode journey bodies consistently for dry runs and scheduled workers. Detect JSON bodies, supply the JSON content type when absent, and honor an explicitly supplied content type. Accept both saved object bodies and user-entered strings.
- Make the sandbox catalog stream one valid JSON array with multiple chunks.
- Run the complete sandbox journey against the in-process API, check token chaining and catalog parsing, and verify explicit content types remain intact.
