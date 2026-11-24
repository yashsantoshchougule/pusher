# F06 Moderate esbuild advisory

The original audit flagged esbuild versions through 0.24.2. Verify the dependency tree from F05's clean installation and compare the resolved version with the advisory range. If it is outside the affected range and the full audit and Vite proxy test pass, close this issue as already resolved by F05. Keep a single dependency change in the lockfile.

Run npm ls esbuild, the full npm audit, and the Vite loopback proxy test on the clean frontend copy. Record the installed esbuild version in the Drive resolution.
