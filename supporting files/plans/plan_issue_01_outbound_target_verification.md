# Issue 01 — Outbound target verification

## Cause and acceptance

The target endpoints, journey executor, and load engine make independent decisions about which destinations they can contact. Require a verified origin for real execution, allow only configured loopback origins for the local sandbox, and ensure the socket connects to an address the destination policy approved.

## Implementation

- Use one canonical HTTP origin for comparisons. Support ordinary paths, exact sandbox aliases, and explicit ports. Reject credentials and invalid or ambiguous origins. Resolve public hostnames for readiness without an HTTP request. Use server-owned sandbox configuration and distinguish DNS readiness from ownership in the frontend.
- Restrict the pre-verification network request to the fixed Guard challenge on the origin used to generate the Guard. Require matching, active verification for load, dry run, and diagnostic calls. Validate journey steps at save and launch and recheck the actual interpolated URL before each send. Ignore caller control over the HTTP Host header.
- Use a destination-bound HTTPX transport for existing outbound clients. Check the resolver's answers immediately before opening a socket, dial a checked numeric address, and preserve the original hostname for TLS verification. Disable redirects and environment proxy routing for these requests.
- Run the regression checks under `supporting files/testing/unit/` with mocked DNS and transport and an isolated SQLite database. Verify accepted paths, refusal of different origins, rejection of non-public production addresses, exact sandbox scoping, DNS-only readiness, and a fixed Guard handshake. Build the frontend to verify the updated status contract.
