# Implementation Plan: Exact Scalable Core + Plugin Architecture Alignment

This plan coordinates aligning all 5 project rule files in `supporting files/rules/` with the exact **Scalable Core + Plugin Architecture Blueprint** specified by the team.

---

## 1. Goal Description

Ensure 100% precision across all documentation, filenames, and architectural specifications so that:
1. `architecture_and_standards.md` uses the exact tree blueprint with filenames (`step_ramp_finder.py`, `api_login_builder.py`, `crash_5xx_breaker.py`, `latency_8s_breaker.py`, `cdn_cache_detector.py`, `pdf_health_card.py`, `mock_target_server.py`, etc.) and all `[Feature #1]`–`[Feature #13]` and `[Memory Rule 3.x]` tags.
2. `team_collaboration.md` matches the exact folder and file boundaries:
   - Partner 1: `backend/` (`core/`, `plugins/`, `api/`), `supporting files/testing/prototypes/`, `benchmarks/`, `unit/`.
   - Partner 2: `frontend/src/core_ui/`, `frontend/src/features/`, and `supporting files/testing/mocks/` (`mock_target_server.py`).
   - REST & WebSocket contracts locked in `backend/core/contracts.py`.
3. `github_workflow.md` reflects this exact structure in ASCII diagrams, responsibilities table, and staging instructions.
4. `target_verification.md` and `safety_limits.md` refer to the exact plugin filenames:
   - `guard_file_verifier.py`
   - `crash_5xx_breaker.py`
   - `waf_429_breaker.py`
   - `latency_8s_breaker.py`
   - `cdn_cache_detector.py`
   - `health_and_disconnect.py`
   - `EmergencyStopButton.jsx`
   - `english_advisor.py`

---

## 2. Invariants & Rules Enforced

- **Simple, Clear, Beginner-Friendly English**: Zero confusing jargon.
- **₹0 Tech Stack**: No paid cloud servers, APIs, or dedicated GPUs.
- **2-Laptop Local Wi-Fi Testing**: Complete isolation between runner and target over Wi-Fi (`0.0.0.0:8080`).
- **RAM Limits**: Strict < 250MB for 1,000 VUs.
- **Testing Directory**: All tests, mocks, prototypes, and benchmarks stay strictly in `supporting files/testing/`.
- **Git Prohibition**: The AI assistant is 100% forbidden from executing `git commit`, `git merge`, `git rebase`, or `git push`.
- **Plans Folder**: All plans stored in `supporting files/plans/`.

---

## 3. Step-by-Step Execution Plan

1. **Update `supporting files/rules/architecture_and_standards.md`**:
   - Replace Section 6 with the exact Scalable Core + Plugin Blueprint tree provided in the prompt.
   - Include `supporting files/plans/` in the tree.
   - Ensure the "How to Add Future Features in 1 File" code sample uses `backend/plugins/traffic_modes/spike_test.py`.
2. **Update `supporting files/rules/team_collaboration.md`**:
   - Align all mentions of plugin and test file names with the new exact blueprint.
   - Verify Rule 1 (Folder Ownership table) and Rule 2 (Contracts).
3. **Update `supporting files/rules/github_workflow.md`**:
   - Verify diagrams and staging commands.
4. **Update `supporting files/rules/safety_limits.md`**:
   - Update breaker file names (`crash_5xx_breaker.py`, `latency_8s_breaker.py`, `cdn_cache_detector.py`).
5. **Update `supporting files/rules/target_verification.md`**:
   - Ensure verifier file references (`dns_txt_verifier.py`, `guard_file_verifier.py`) are consistent.
6. **Update `supporting files/plans/README.md`**:
   - Add this plan to the index.
