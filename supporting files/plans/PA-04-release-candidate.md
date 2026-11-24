# PA-04 — Prepare a reproducible reviewed release candidate

Priority: Must Fix

Master: https://docs.google.com/document/d/1J9sPxjf_nf7PTuI4aV27e3jL_5rZ59tQ5bM4b3ZOEAs/edit?usp=drivesdk

## Task prompt

Prepare a reproducible candidate from this working tree and identify the exact release gate. Use a fresh isolated copy with no real .env, database, or existing dependency directories. Resolve only verified reproducibility faults. Demonstrate locked installs, backend and frontend tests, a production build and the existing loopback sandbox workflow. After later backlog fixes, refresh the candidate and repeat all checks.

## Observed state

The local tree carries source, test, lockfile and documentation changes beyond main at abf2e1e. pyproject.toml, uv.lock and .python-version are still untracked. No tracked CI workflow was found. The Git workflow assigns staging, commits, branches and pushes to the human developer. Report candidate validation independently of publication and review.

## Implementation and checks

1. Copy only tracked and nonignored application and test files plus the lockfiles to a dedicated new temporary directory. Exclude environment files except checked-in examples, real SQLite databases and credentials.
2. Run `uv sync --locked` and `npm ci --prefix frontend` from the copy. Use the locked Python interpreter, the Node unit suite, the clock tests, the production build, and the repository sandbox verification script on disposable SQLite.
3. Record exact results and create a handoff with clean-checkout commands and the manual review dependency. Include existing environment prerequisites and verify no package or source version was inferred.
4. Candidate copies are disposable. The repository source and Git index require no release-task mutation. The published candidate is blocked until a human reviews, commits, and pushes it and the resulting clean checkout passes these gates.

## Candidate findings

- This host's uv could not discover or download the pinned runtime. Supplying the installed Python 3.12.14 binary via `uv sync --locked --python <path>` resolved discovery and installed 39 packages. `npm ci --prefix frontend --no-audit --no-fund` installed 147 packages.
- A cold Vite proxy integration wrote optimizer files under the installed frontend tree. The clean Windows candidate refused the rename and the check failed with EPERM. Disable prebundling for this test, which exercises only Vite's HTTP proxy and WebSocket upgrade. Production and development configuration keep their normal optimizer settings.

## Initial candidate evidence and release handoff

The isolated candidate passed 182 backend tests with outbound HTTPX transports disabled, 73 Node unit tests, 10 clock boundary checks, the production build, and the offline sandbox flow through report export. The release ref remains pending a human-reviewed commit. The committed candidate needs these same checks from a clean clone, followed by the staging checks in PA-08 through PA-11.

```powershell
uv sync --locked
npm ci --prefix frontend
uv run --locked python -B -m pytest -q -p no:cacheprovider
node --test (Get-ChildItem -LiteralPath 'supporting files/testing/unit' -Filter 'test_*.mjs' | ForEach-Object FullName)
node 'supporting files/testing/unit/test_time_mapping.cjs'
uv run --locked python -B 'supporting files/testing/verification/check_local_sandbox.py'
npm run build --prefix frontend
```

## Final candidate evidence

The refreshed candidate with all local remediation changes passed 182 backend tests with outbound HTTPX blocked, 76 Node unit tests, all 10 clock checks, the no-environment production build, and the loopback sandbox flow through report export. The optional Flask Guard check also passed. Source and test changes remain in the working tree for manual review and publication.

