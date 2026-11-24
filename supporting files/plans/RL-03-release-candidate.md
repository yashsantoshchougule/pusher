# RL-03 — Prepare and verify a release

Must Fix. Source item 3 in the original release audit and task 2 in the current local workflow. [Terms approval and verification](RL-02-terms-publication.md)

Prepare a fresh, isolated copy of the reviewed local changes, including RL-01, RL-02, and the 4,096 MB RAM ceiling. Exclude real environment files, local databases, ignored and installed dependencies, and Git metadata. Record the base commit and a digest of the copied inputs.

1. Run `uv sync --locked` and `npm ci --prefix frontend` in the isolated directory. Record any runtime prerequisite or fallback. Keep lockfiles unchanged.
2. Run `python -B -m pytest -q -p no:cacheprovider` using the synced environment, the Node unit suite, the clock check, Vite production build, controlled sandbox smoke through export, and optional offline Flask adapter check if available. Cover 4,096 MB on large hosts, the lower 75% rule for small hosts, and upper-bound rejection. Isolate fixtures and do not target live services.
3. Report the candidate results and gate status. Once the owner publishes a reviewed commit, repeat from a clean checkout of that commit and then verify PA-08 through PA-10 on authorized staging using disposable accounts and a WAF-protected test target. Terms approval is required before release. Record each hosted check independently.

## Candidate evidence

- Base commit `cd9dc7ac3a77e19efea764c9064e95774bc63431`, with the local RAM, startup, and account changes applied. The 343 copied inputs hashed to SHA-256 `b2d5790139e290788ea10c24f259950e9989ef024192439d817a6b3a953849cf` using sorted relative paths and per-file SHA-256 digests. This is a source snapshot, not a published commit.
- The installed uv could not find Python 3.12.14. `uv sync --locked --python <installed CPython 3.12.13>` installed 39 locked packages. The allowed base Python used the candidate's installed packages to run checks. `npm ci --prefix frontend --no-audit --no-fund` installed 147 packages.
- Pytest with `-q -p no:cacheprovider` and non-loopback HTTPX transports rejected: 185 passed, including 4 GB ceiling, smaller-host cap, persistence, and rejection regressions. Eleven deprecation warnings.
- All discovered `test_*.mjs` files: 86 passed. `test_time_mapping.cjs`: 10 checks passed. `npm run build --prefix frontend` passed with no application environment. The existing proxy fixture logged a Tailwind content warning.
- `check_local_sandbox.py` passed through report export. `check_flask_guard.py` passed with Flask 3.1.2 installed only in the scratch candidate.
- Exact runtime follow-up: the official Astral Windows 3.12.14 archive matched the published SHA-256. A separate locked sync with that runtime succeeded. All 185 backend tests, the sandbox export smoke, and the Flask Guard fixture passed on 3.12.14. An initial standalone smoke reported a Windows SQLite DLL block. A fresh process imported SQLite successfully and passed the smoke.
- Pending: approved Terms, reviewed release revision, hosted email/Google/GitHub, HTTPS and WSS, and deployed Guard/WAF verification.

## Refreshed candidate after recovery fix

- The fresh source snapshot contains 346 files and has SHA-256 `4bf054eb2c79408e6b80a53afbc8ed0ded8636aa1c6aac758b07ae03877be31a` using the same digest procedure. This supersedes the previous local snapshot.
- Locked installs used Python 3.12.14 and a clean npm install. The isolated pytest suite passed **185 tests** with outbound HTTPX blocked. The Node suite passed **87 tests**, and all **10** clock checks passed. The production build without Vite provider settings, the sandbox export smoke, and the isolated Flask Guard check passed.
- The pending release and staging gates above still apply. Repeat the gates from the owner-reviewed published commit.

## Current task prompt — Verify the published candidate

Prepare the owner-reviewed release containing the approved Terms, one-command startup, account recovery, and the 4 GB RAM ceiling. Review the working-tree file inventory and separate actual release inputs from environment files and databases. The project owner stages, commits, and pushes. Once published, clone the repository into a disposable local directory, check out the exact published commit, and confirm `HEAD` and a clean initial `git status`. Verify that the commit includes all four changes before running tests.

With Python 3.12.14 and no real provider configuration, run the commands below in that clean checkout. The test database and sandbox data must be disposable. Keep the ordinary browser and cloud settings out of the run. Record the revision, commands, counts, and status in this plan. This task covers clean-checkout verification. Hosted staging remains separate.

```powershell
uv sync --locked
npm ci --prefix frontend
uv run --locked python -B -m pytest -q -p no:cacheprovider
$ReleaseNodeTests = Get-ChildItem -LiteralPath 'supporting files/testing/unit' -Filter 'test_*.mjs' | ForEach-Object FullName
node --test $ReleaseNodeTests
node 'supporting files/testing/unit/test_time_mapping.cjs'
npm run build --prefix frontend
uv run --locked python -B 'supporting files/testing/verification/check_local_sandbox.py'
```

Accept the release candidate only if the exact published commit passes every required check, the sandbox produces a finalized export, and the lockfiles remain unchanged. Record failed checks against their exact revision and repeat after a corrected candidate is published.

## Local handoff after Terms approval

- Task 1 passed. The Terms page and consent control use the approved copy, and the exact words and consent transitions passed automated and browser checks.
- The local snapshot used Python 3.12.14 with the previously locked packages. It contained 251 files without real environment files, database files, or plan records. SHA-256 over sorted relative paths, a tab, and each file's SHA-256 joined with LF was `a97799a95d29e08b7ecafb34ac17c47608e2a217dc20b3bbf55fa3018fbcef1e`. All 185 backend tests and the loopback sandbox through finalized export passed. The working-tree frontend passed 89 Node unit tests, all 10 clock checks, and the production build. Pytest reported 11 deprecation warnings, and Vite reported the existing large chunk warning.
- Review the working-tree changes and new files using `git status --short`, `git diff --`, and `git ls-files --others --exclude-standard`. Include the new startup launcher, recovery helper and page, Terms page, and their regression tests when selecting release files. The app, profile, and traffic changes include the 4 GB RAM ceiling. Keep local credentials and SQLite data out of the reviewed commit.
- `git ls-remote --heads origin` on 24 November 2026 showed only `main` at `cd9dc7ac3a77e19efea764c9064e95774bc63431`. The previous package installation and local passing checks prepare the candidate. The release acceptance check still requires locked installs and all commands above from the exact owner-published commit.

## Fresh locked-install rehearsal

On 24 November 2026, reran the release commands from a disposable, environment-free copy of the same 251-file local snapshot. Its SHA-256 matched the handoff above. `uv sync --locked --python <Python 3.12.14>` and `npm ci --prefix frontend --no-audit --no-fund` succeeded. The backend checks used that interpreter with the freshly installed environment packages and restricted HTTPX to loopback.

- 185 backend tests, 89 Node unit tests, and 10 clock checks passed with zero failures and zero skips. The production build and loopback sandbox through finalized report export passed. Both lockfiles were unchanged.
- Pytest emitted 11 existing deprecation warnings. npm reported one uncovered esbuild install script. The installed toolchain completed the tests and build with the existing npm script policy.
- GitHub still exposed only `main` at `cd9dc7ac3a77e19efea764c9064e95774bc63431` when the rehearsal began. The local candidate is ready for owner review and publication. The published commit remains the input for the final verification pass.
