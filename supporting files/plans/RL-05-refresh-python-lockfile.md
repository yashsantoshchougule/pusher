# RL-05 — Update the Python lockfile

Must Fix. First issue in the current release backlog. Keep the prompt and result in the local project.

## Execution prompt

Bring `uv.lock` into sync with the existing backend dependency manifest. A clean install must use the same Python range and declared dependencies as `pyproject.toml`, while retaining the existing Python 3.12.14 developer pin and Windows and POSIX event-loop markers.

1. Confirm the baseline by comparing the Python constraint and dependency entries in `pyproject.toml` and `uv.lock`. The current lock lacks `aiohttp`, `reportlab`, and `winloop`, and its Python constraint differs from the manifest.
2. Copy both manifests to a disposable directory and run `uv lock --python <Python 3.12.14>` using the project’s existing lock to retain compatible versions. Verify `uv lock --check` and run a fresh `uv sync --locked` from the same directory. Check that `aiohttp`, `reportlab`, and the Windows loop module import from the install. Confirm `uvloop` remains in the universal lock with the POSIX marker.
3. Confirm the workspace manifest and original lock did not change during verification, then copy back the generated `uv.lock`. Verify the digest and inspect the lockfile diff. Leave application source and the existing `.venv` alone.
4. Record the actual commands and result here. Move to the combined UI and backend test only after the clean locked install passes.

## Verification result

Resolved. With CPython 3.12.14, `uv lock --python <interpreter>`, `uv lock --check --python <interpreter>`, and `uv sync --locked --python <interpreter>` all passed in a disposable Windows directory. The solver resolved 54 packages and the fresh environment installed 52 packages. `aiohttp` 3.14.5, `reportlab` 4.5.1, and `winloop` 0.8.4 imported successfully. The lock includes `uvloop` 0.23.0 for non-Windows systems and matches the project's Python range. POSIX execution was not exercised here.

Only the verified `uv.lock` was copied to the project. SHA-256 `6f605daf691bd05a87f326f281c7fb4d77665b44255448f554c3e8e99dd4825c`. The existing development environment was not modified.
