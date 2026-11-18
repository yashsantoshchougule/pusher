# Technical Plan: Modular Wireframe Dashboard with Dedicated Sub-Views (Option B)

## Context & Objectives
Refactor `DashboardPage.jsx` into Option B architecture:
- `1. Dashboard` is a pure read-only summary screen matching the 3-box wireframe layout with zero duplicate controls.
- `2. Verify Target` houses the complete interactive Target Verification Wizard + WAF Guide preview and modal.
- `3. Traffic Setup` houses the full interactive traffic mode configurator, VU slider, safety circuit breakers, and resource estimator.
- `4. API Builder` houses the multi-step request chain builder.
- `5. Reports` houses the Saturation Knee breakdown and Baseline comparison table.
- Strict binary black-and-white wireframe styling (`bg-white`, `text-black`, `border-2 border-black`, `font-mono`, zero color).
