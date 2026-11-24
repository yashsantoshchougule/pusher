# Project Architecture & Implementation Plans

This folder stores all architectural plans, technical design specifications, and feature roadmaps for **Pusher**.

---

## 📋 Plan Naming Convention

Project-wide plans use this format. Audit remediation plans start with their issue ID.

```text
plan_<feature_or_component_description>.md
```

### Examples:
- `plan_scalable_core_and_plugin_architecture.md` — Technical blueprint for Frozen Core and plug-and-play plugins.
- `R06-ownership-only-guard.md` — Ownership-only Guard and target security controls.
- `plan_rules_and_security_loophole_hardening.md` — Initial audit hardening for SSRF, memory caps, and circuit breakers.

---

## 🗂️ Plan index

| Plan File | Purpose & Scope |
| :--- | :--- |
| [`plan_500mb_ram_ceiling_and_hardware_scaling.md`](plan_500mb_ram_ceiling_and_hardware_scaling.md) | Technical plan to update all project Markdown rules, architecture, and testing documentation to the 500 MB default RAM ceiling (2,250 VUs) and user-expandable hardware RAM scaling model. |
| [`plan_test_history_and_dashboard_cleanup.md`](plan_test_history_and_dashboard_cleanup.md) | Technical plan to add dedicated `5. Test History` page, expand left sidebar to 6 navigation views, and isolate Box 3 on `1. Dashboard` strictly to live telemetry stream. |
| [`plan_modular_wireframe_dashboard.md`](plan_modular_wireframe_dashboard.md) | Technical plan for Option B: refactoring `DashboardPage.jsx` into a pure read-only 3-box summary screen with dedicated interactive views for Verify Target, Traffic Setup, API Builder, and Reports. |
| [`plan_wireframe_dashboard.md`](plan_wireframe_dashboard.md) | Technical implementation plan to build the high-fidelity black-and-white wireframe Dashboard (`DashboardPage.jsx`) with interactive React state, SSRF guard, 48h countdown, traffic launcher, live telemetry, and circuit breakers. |
| [`plan_responsive_login_scaling.md`](plan_responsive_login_scaling.md) | Technical implementation plan and root-cause analysis for fluid, adaptive responsive scaling of `LoginPage.jsx` across Mobile, Tablet, Laptop, and Monitor screens. |
| [`plan_palette_migration_taupe_sage_bone.md`](plan_palette_migration_taupe_sage_bone.md) | Technical implementation plan for migrating Pusher to the 4-color Earthy Taupe, Sage & Bone palette (`#A49A87`, `#A5A58D`, `#968F83`, `#E8E5DF`). |
| [`plan_dashboard_sage_palette.md`](plan_dashboard_sage_palette.md) | Technical implementation plan to migrate `DashboardPage.jsx` to the unified Sage Green, Olive, and Cream palette matching `LoginPage.jsx` and user-uploaded reference. |
| [`plan_dashboard_page_implementation.md`](plan_dashboard_page_implementation.md) | Technical implementation plan for building the complete Pusher Mission Control Dashboard (`DashboardPage.jsx`) and wiring into `App.jsx`. |
| [`plan_supabase_authentication_integration.md`](plan_supabase_authentication_integration.md) | Technical implementation plan to integrate Supabase Authentication with client-safe key isolation, login/signup handlers, and session management. |
| [`plan_left_panel_clarity_and_full_bleed.md`](plan_left_panel_clarity_and_full_bleed.md) | Technical implementation plan to enhance image clarity, brightness, saturation, and full-bleed sizing on the left visual panel of `LoginPage.jsx` with bottom-only vignette. |
| [`plan_dynamic_100_frame_timelapse.md`](plan_dynamic_100_frame_timelapse.md) | Technical plan to dynamically display the 100-frame sequence (`ezgif-frame-001.jpg` – `100.jpg`) on the left visual panel in `LoginPage.jsx` based on the user's real-time local clock. |
| [`plan_left_panel_custom_background_image.md`](plan_left_panel_custom_background_image.md) | Implementation plan for setting a custom moody dark sage-green & olive minimalist landscape background image with a dark gradient scrim overlay on the left panel. |
| [`plan_olive_sage_cream_luminance_hierarchy.md`](plan_olive_sage_cream_luminance_hierarchy.md) | Technical implementation plan for applying the Earthy Olive & Sage palette with the explicit area-luminance hierarchy (lightest on largest, darkest on focal CTAs). |
| [`plan_methodical_research_and_verification_engine.md`](plan_methodical_research_and_verification_engine.md) | Technical implementation plan for codifying the Methodical Research & Verification Engine directive and enforcing the official 5-color palette tokens. |
| [`plan_palette_migration_to_charcoal_silver_cream_slate.md`](plan_palette_migration_to_charcoal_silver_cream_slate.md) | Technical implementation plan for migrating Pusher to the new 4-color palette (`#4A4A4A`, `#CBCBCB`, `#FFFFE3`, `#6D8196`). |
| [`plan_split_screen_login_authentication_page.md`](plan_split_screen_login_authentication_page.md) | Technical implementation plan for the pixel-accurate dark split-screen authentication page (`src/pages/LoginPage.jsx`) matching the reference image. |
| [`plan_pixel_accurate_starter_page_implementation.md`](plan_pixel_accurate_starter_page_implementation.md) | Technical implementation and visual verification loop for the pixel-accurate Pusher Starter Page in `frontend/src/pages/StarterPage.jsx`. |
| [`plan_pixel_perfect_interface_replication.md`](plan_pixel_perfect_interface_replication.md) | Pixel-perfect replication of the Pusher Hero landing page, bento grid capacity dashboard, and trust badges using the official 5-color palette. |
| [`plan_frontend_color_palette_design_tokens.md`](plan_frontend_color_palette_design_tokens.md) | Official 5-color hex design token system (`#FFFFFF`, `#242424`, `#5C7C89`, `#1F4959`, `#011425`) for dashboard, charts, and bento UI. |
| [`plan_remove_hardcoded_roles_and_refactor_local_testing.md`](plan_remove_hardcoded_roles_and_refactor_local_testing.md) | Removes hardcoded 2-person and 2-laptop roles, establishes flexible team ownership and local mock server testing (`PUSHER_MODE=local_dev`). |
| [`plan_exact_scalable_blueprint_alignment.md`](plan_exact_scalable_blueprint_alignment.md) | Exact alignment of all 5 rule files to the finalized Scalable Core + Plugin architecture blueprint. |
| [`plan_scalable_core_and_plugin_architecture.md`](plan_scalable_core_and_plugin_architecture.md) | Scalable Core + Plugin architecture blueprint with exact feature and memory rule mappings. |
| [`plan_2in1_pusher_guard_middleware_upgrade.md`](plan_2in1_pusher_guard_middleware_upgrade.md) | Superseded by [the ownership-only Guard plan](R06-ownership-only-guard.md). |
| [`plan_2person_team_collaboration_and_wifi_testing.md`](plan_2person_team_collaboration_and_wifi_testing.md) | Superseded by [flexible team roles and local testing](plan_remove_hardcoded_roles_and_refactor_local_testing.md). |
| [`plan_rules_and_security_loophole_hardening.md`](plan_rules_and_security_loophole_hardening.md) | Deep audit of SSRF defenses, memory limits (<500MB default, scalable), and circuit breakers. |

---

The plan index records design intent. Use the current code and verification results to establish implementation status.
