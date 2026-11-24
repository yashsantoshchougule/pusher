# R09 The WAF screen can claim success from one 200 OK

Should Fix. [Pusher Remediation — Remaining Issues](https://docs.google.com/document/d/1RpVDZM22lKwMj5eGugDi6j5t_-obO1TfsMldBH5kJQI/edit)

The diagnostic API treats a single success response as proof of an edge exemption, and a browser network failure can produce a fabricated success. Several workflow instructions still describe Guard headers that are no longer sent.

1. Send one ordinary HEAD request to the verified origin using the checked transport, no redirects and no private query or Guard credentials. Return actual HTTP status, elapsed time, and a header-based provider hint. Explain 403, 429, unsupported methods and connection failures in terms of the observed response.
2. In sandbox mode mark simulation and omit measured fields. In the browser show transport failures as errors and keep simulation clearly labeled. Update the operator instructions to describe ownership and diagnostic checks.
3. Run pytest on edge diagnostics, Stage 1, target privacy, and outbound policy. Mock HTTP 200, 403, 429, 405, 501 and connection failure. Verify the probe has no Guard credentials or query, and sandbox makes no call. Include the WAF screen in the Vite build.

The route path stays stable while its response fields change with the dashboard. This does not configure edge policies or establish performance under load.
