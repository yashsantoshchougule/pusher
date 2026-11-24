# F05 High-severity Vite advisory

The lockfile resolves Vite 5.4.21. Move to Vite 6.4.6, the patched release on the nearest compatible major line. The installed React plugin supports Vite 6, Node 24 satisfies the engine range, and the current Rollup fallback meets the new dependency range. Preserve the loopback dev-server proxy.

Regenerate the lockfile with npm and use a clean npm ci. Require zero vulnerabilities in the full and production-only audits. Run the existing browser API and WebSocket proxy regression and the production build. Record any transitive advisory resolution in its own issue.

Sources: https://github.com/vitejs/vite/releases/tag/v6.4.6 and https://github.com/vitejs/vite/security/advisories.
