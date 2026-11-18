# Technical Plan: 500 MB Default RAM Ceiling & Hardware RAM Scaling Rules

## Context & Objectives
Update all Markdown rule, architecture, and testing documentation files across the workspace:
- Upgrade legacy baseline cap (`250 MB` / `1,000 VUs`) to the new **`500 MB` default ceiling (`2,250 VUs`)**.
- Maintain unchanged per-user memory footprint of `0.20 MB` (`200 KB`) via 4 KB streaming chunk discards.
- Formalize dynamic formulas:
  - `Estimated RAM (MB) = 50 + (Active VUs × 0.20)`
  - `Max Allowed VUs = floor((Allocated RAM Limit MB - 50) / 0.20)`
- Introduce user-expandable hardware RAM scaling tiers (500 MB -> 2,250 VUs, 1 GB -> 4,870 VUs, 2 GB -> 9,990 VUs, 4 GB -> 20,230 VUs).
- Enforce Host Safety Ceiling (capped at 75% of total hardware RAM and 70% OS File-Descriptor limit).
- **Strict Constraint**: Modify ONLY Markdown (`.md`) files; zero source code or config files touched.
