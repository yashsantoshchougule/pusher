# Technical Plan: Dedicated Test History Archive & Dashboard Telemetry Isolation

## Context & Objectives
1. Expand left sidebar navigation to 6 distinct items (`1. Dashboard`, `2. Verify Target`, `3. Traffic Setup`, `4. API Builder`, `5. Test History`, `6. Reports`).
2. Clean `1. Dashboard` Box 3 into a pure real-time telemetry stream monitor, removing the history table tab and adding a `[ VIEW TEST HISTORY ARCHIVE (X) → ]` link.
3. Build the dedicated `5. Test History` view with search, mode/status filters, clone config action, and 2-run checkbox selection feeding into `6. Reports` baseline comparison.
4. Maintain strict black-and-white wireframe aesthetics (`bg-white`, `text-black`, `border-2 border-black`, `font-mono`, zero color).
