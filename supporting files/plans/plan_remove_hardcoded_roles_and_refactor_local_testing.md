# Implementation Plan: Remove Hardcoded 2-Person & 2-Laptop Setup across Rules

This plan outlines the systematic removal of all hardcoded "2-person team", "Partner 1 / Partner 2", and "2-laptop (Laptop 1 / Laptop 2)" references across all project rule files in `supporting files/rules/`.

---

## 1. Goal Description

Transition the Pusher documentation from a rigid 2-person, 2-laptop constraint to a flexible, professional team architecture:
1. **Flexible Role Distribution**:
   - Eliminate all hardcoded "Partner 1" and "Partner 2" assignments.
   - Replace with flexible ownership where developers and project leads assign tasks and branch responsibilities dynamically based on sprint requirements.
2. **Local Development & Mock Target Testing (`PUSHER_MODE=local_dev`)**:
   - Replace the "2-laptop" setup with a clean local testing architecture.
   - Developers run the mock target server (`supporting files/testing/mocks/mock_target_server.py` on `0.0.0.0:8080`) locally on the same machine (on a separate port) or on any machine over the local network.
3. **Exact Blueprint Matching**:
   - Update Section 6 of `architecture_and_standards.md` to the clean blueprint without partner ownership labels.
4. **Preserve All Security & Memory Guardrails**:
   - RAM budget (<250MB for 1,000 VUs).
   - ₹0 tech stack.
   - 3 circuit breakers and 2-in-1 `pusher_guard` middleware.
   - Strict rule: AI is 100% forbidden from executing `git commit`, `git merge`, `git rebase`, or `git push`.
   - All tests/mocks strictly in `supporting files/testing/`.

---

## 2. File-by-File Changes

### 1. `architecture_and_standards.md`
- **Section 2**: Replace "Project Hardware & The 2-Laptop Setup" with **"Consumer Hardware Efficiency & Local Mock Testing"**:
  - Focus on running on standard consumer hardware (16GB RAM, 512GB SSD) with zero dedicated GPU required.
  - Describe the local mock server testing setup (`mock_target_server.py` on `0.0.0.0:8080`) under `PUSHER_MODE=local_dev`.
- **Section 6**: Replace Section 6 directory tree with the exact clean Scalable Core + Plugin blueprint (zero partner ownership annotations).

### 2. `team_collaboration.md`
- Retitle and refocus as **"Team Collaboration & Agile Development Standards"**.
- Remove ASCII diagram with "PARTNER 1 (Laptop 1)" and "PARTNER 2 (Laptop 2)".
- Replace with a clean Git feature branching workflow (`feature/*` -> Pull Request -> `main`).
- Replace the rigid Partner 1 / Partner 2 table with **"Modular Subsystem Architecture & Ownership"**:
  - Backend & Engine subsystem (`backend/core/`, `backend/plugins/`, `backend/api/`).
  - Frontend UI subsystem (`frontend/src/core_ui/`, `frontend/src/features/`).
  - Testing & Quality subsystem (`supporting files/testing/`).
  - Task and branch assignments are assigned flexibly by the developer or project lead.
- Keep Rule 2 (API Contract First) with `backend/core/contracts.py`.
- Keep manual Git workflow and AI prohibition.

### 3. `github_workflow.md`
- Remove all references to "2-person team", "Partner 1", "Partner 2", "backend-dev", and "frontend-dev".
- Replace branch model with standard feature branching (`feature/<name>` or component branches assigned per developer) merging into `main` via PR.
- Keep the strict AI Git prohibition.

### 4. `target_verification.md` & `safety_limits.md`
- Ensure all references to Laptop 2 are replaced with "Mock Target Server" or "Local Network Host (`PUSHER_MODE=local_dev`)".
- Check Firewall Bypass Troubleshooting Box in `safety_limits.md` to reference "Local Mock Target Testing (`PUSHER_MODE=local_dev`)" instead of "2-Laptop Wi-Fi setup".

### 5. `supporting files/testing/README.md` & Root `README.md`
- Update headings and descriptions to reference "Local Development & Mock Target Testing" instead of "2-Laptop setup".
- Remove "2-Person Development Team" section from root `README.md` and replace with "Modular Subsystems & Flexible Roles".

---

## 3. Verification

- Grep for `Partner 1`, `Partner 2`, `2-Person`, `2-Laptop`, `Laptop 1`, `Laptop 2` across the entire workspace to ensure 100% elimination.
- Verify that `git status` shows clean modifications.
- Confirm AI executed zero Git commands.
