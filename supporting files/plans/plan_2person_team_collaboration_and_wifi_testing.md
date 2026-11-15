# Implementation Plan: 2-Person Team Collaboration Rule & Architectural Alignment

## Goal Description
Create a new comprehensive rule file at `supporting files/rules/team_collaboration.md` defining strict 2-person team collaboration guidelines, zero merge conflict boundaries, the API Contract First rule, the 2-laptop Wi-Fi testing protocol, environment synchronization rules, and AI assistant boundaries. 
Simultaneously, update `architecture_and_standards.md` and `github_workflow.md` to reference the new collaboration file and harmonize branch names (`backend-dev` and `frontend-dev`) and testing roles.

---

## User Review Required
> [!IMPORTANT]
> **Branch Naming Standardization**: Aligning branch names to `backend-dev` (Partner 1) and `frontend-dev` (Partner 2) across all documentation for consistency.
> **Strict AI Governance Invariant**: Re-affirming across all documents that the AI is 100% forbidden from executing `git commit`, `git merge`, `git rebase`, or `git push`.
> **Zero Merge Conflict Boundaries**: Clear physical folder separation where Partner 1 owns `backend/` + prototypes/benchmarks, and Partner 2 owns `frontend/` + mocks.

---

## Proposed Changes

### [NEW] `supporting files/rules/team_collaboration.md`
Create the dedicated collaboration guide featuring:
1. **Strict Role & Folder Ownership**:
   - Partner 1 (Backend, Security & Load Engine): owns `backend/`, `supporting files/testing/prototypes/`, `supporting files/testing/benchmarks/`.
   - Partner 2 (Frontend UI, Charts & Mocks): owns `frontend/`, `supporting files/testing/mocks/`.
   - Shared files rule: strict permission required before editing each other's directories; all test scripts stay in `supporting files/testing/`.
2. **The "API Contract First" Rule**:
   - Both partners must agree on JSON contracts before code changes.
   - REST endpoints specification (`/api/v1/test/start`, `/api/v1/test/stop`, `/api/v1/verify/*`).
   - 1-second WebSocket / SSE live telemetry JSON message format (`active_vus`, `current_rps`, latency percentiles, status counts, breaker alerts).
   - Advance notification requirement before any key renaming.
3. **2-Person Manual Git & Branching Workflow**:
   - `main`: Production-ready code only.
   - `backend-dev`: Partner 1's branch.
   - `frontend-dev`: Partner 2's branch.
   - Daily sync protocol: manual `git pull origin main`, manual staging of owned folders, manual commit, mutual PR review.
4. **Two-Laptop Hardware & Wi-Fi Testing Protocol**:
   - Hardware details: Two 16GB RAM / 512GB SSD laptops (one with RTX 4050).
   - Laptop 1: Runs Pusher backend and frontend dashboard (< 250MB RAM target).
   - Laptop 2: Runs mock target endpoints (`supporting files/testing/mocks/`) on port 8080.
   - Local Wi-Fi test mode: `PUSHER_MODE=local_dev` testing `http://192.168.x.x:8080` without public DNS or cloud costs.
5. **Shared Environment & Setup Rules**:
   - Synchronized Python 3.11+ and Node.js versions.
   - Immediate recording of Python dependencies in `backend/requirements.txt` and npm packages in `frontend/package.json`.
   - Strict ban on committing `.env`, `node_modules/`, `venv/`, `__pycache__/`, logs. Safe `.env.example` provided.
6. **AI Assistant Rules for Both Teammates**:
   - AI on both laptops must read `supporting files/rules/` before writing code.
   - AI strictly forbidden from installing headless browsers (Selenium, Playwright, Puppeteer), putting test files outside `supporting files/testing/`, or executing Git commits/pushes.
7. **Comprehensive Dual-Track ASCII Diagram**:
   - Illustrating Git branch flow (`backend-dev` + `frontend-dev` -> PR -> `main`) alongside the live local Wi-Fi testing interaction (Laptop 1 -> Wi-Fi -> Laptop 2).

---

### [MODIFY] `supporting files/rules/architecture_and_standards.md`
- Add `team_collaboration.md` to the directory tree in Section 6.
- Add reference link to `team_collaboration.md` in Section 2 (Project Hardware & The 2-Laptop Setup) for full collaboration and API contract details.

---

### [MODIFY] `supporting files/rules/github_workflow.md`
- Update branch names from `backend-engine` / `frontend-and-mocks` to `backend-dev` / `frontend-dev`.
- Add explicit cross-reference to `team_collaboration.md` for role definitions, API contracts, and environment sync rules.

---

## Verification Plan

### Automated / Manual Inspection
- Confirm `supporting files/rules/team_collaboration.md` is created with all 6 core rules and the ASCII diagram.
- Verify `architecture_and_standards.md` and `github_workflow.md` correctly reference `team_collaboration.md`.
- Verify that all directory paths across all files strictly use `supporting files/` (with a space).
- Ensure simple, beginner-friendly language and confirm that the strict Git rule is prominently emphasized.
