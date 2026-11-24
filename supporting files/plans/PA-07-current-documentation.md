# PA-07 — Align setup and safety documentation with current behavior

Priority: Should Fix

Master: https://docs.google.com/document/d/1J9sPxjf_nf7PTuI4aV27e3jL_5rZ59tQ5bM4b3ZOEAs/edit?usp=drivesdk

## Task prompt

Make first-run and safety documentation match the current code. Describe pinned install, explicit shared sign-in, loopback sandbox, and the tested circuit thresholds. Qualify unsupported latency and memory promises. Mark replaced security and ownership plans as historical. Keep documentation changes targeted and leave runtime policy untouched.

## Verified baseline

README.md advertises a guaranteed measured 500 MB at 2,250 VUs and sub-200 ms Stop, links to superseded Guard behavior, and conflates the built-in and standalone mocks. The testing guide repeats the latency claim and has unused benchmark/prototype paths. The target rules contain an old local-network and verification summary. The plan index calls older bypass and role designs current. Verify statements against config.py, target_policy.py, auth_deps.py, circuit_breakers.py, load_engine.py, current README/config examples, and the earlier local verification.

## Implementation and acceptance

1. Update the project and testing READMEs to show reproducible commands, Python discovery fallback, configured shared auth, measured outcomes versus model limits, and existing smoke checks.
2. Correct the active local target section. Mark unimplemented safety designs as planned and old Guard and team designs as superseded.
3. Validate all updated links and documented files. Run the documented local build, suites, and sandbox smoke check from the clean candidate. Keep claims specific to those results.
4. Revert the documentation blocks to roll back. This task does not change permissions, caps, or runtime configuration.

