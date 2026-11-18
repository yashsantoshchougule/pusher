# GitHub Version Control & Development Workflow

> [!CAUTION]
> ## STRICT AI GOVERNANCE RULE
> **The AI assistant / system is 100% strictly forbidden from pushing code to GitHub by itself.**
> **All git commits, branch merges, and pushes must be executed manually by the human developer. No exceptions.**

---

## 1. Why Git Actions Must Be Manual
Automated AI commits and pushes can accidentally leak private API keys, break working branches, or push untested code to GitHub.

To maintain complete human sovereignty and project safety:
1. **The AI only writes and edits files locally** in your workspace.
2. **Only human developers** have the right to inspect diffs, stage files, write commit messages, and push to GitHub.

---

## 2. Modular Architecture & Feature Branching

Pusher utilizes a modular subsystem architecture to keep development clean and prevent merge conflicts:

```
                                [ main Branch ]
                     (Production-ready, tested code only)
                                      ▲
                                      │ Pull Request Review & Merge
                  ┌───────────────────┴───────────────────┐
                  │                                       │
      [ feature/backend-engine ]              [ feature/frontend-ui ]
        (Engine, Plugins & APIs)                (Dashboard & Charts)
  • backend/core/ (Frozen Core)               • frontend/src/core_ui/ (Always-on Controls)
  • backend/plugins/ (Pluggable Features)     • frontend/src/features/ (Modular UI Cards)
  • backend/api/ (REST & WebSocket)           • supporting files/testing/mocks/ (Mock Targets)
  • supporting files/testing/prototypes/      • Live Speed & Latency Percentile Charts
  • supporting files/testing/benchmarks/      • Big Red Emergency Stop Button (<200ms)
  • SSRF Blocker & Safe DNS Pinning           • Verification Wizard Modal & Forms
```

> **Task & Branch Assignments**: Task distribution, file editing, and branch assignments are managed flexibly by the developer or project lead based on active project goals. Developers create dedicated feature branches (`feature/<feature-name>`), test their changes, and merge into `main` via reviewed Pull Requests.

---

## 3. The Human Developer's Step-by-Step Git Workflow

All code changes follow this sequential manual process:

```
    [ AI generates or updates local code ]
                         │
                         ▼
        [ Step 1: Human checks git status & diff ]
                         │
                         ▼
        [ Step 2: Human runs local tests & checks ]
                         │
                         ▼
        [ Step 3: Human explicitly stages files ]
             git add <folder-name>
                         │
                         ▼
        [ Step 4: Human makes a descriptive commit ]
             git commit -m "feat: description"
                         │
                         ▼
        [ Step 5: Human pushes to their branch ]
             git push origin <branch-name>
                         │
                         ▼
        [ Step 6: Create GitHub Pull Request (PR) ]
```

---

### Step 1: Check Your Changes
Always inspect what was changed before touching anything in Git:
```bash
git status
git diff
```

### Step 2: Run the Pre-Commit Security Checklist
Before staging, verify that your code adheres to all project rules:
- [ ] **No Secret Keys**: Ensure `.env` and sensitive tokens are NOT staged.
- [ ] **Folder Structure**: All test scripts, mock servers, and benchmarks are inside `supporting files/testing/`.
- [ ] **No Headless Browsers**: No Playwright, Puppeteer, or Selenium imported.
- [ ] **Zero Full-Page Buffering**: Responses are streamed in small 4KB chunks and discarded.
- [ ] **Tests Pass**: Run your unit tests and mock server checks locally.

### Step 3: Explicitly Stage Your Files
Avoid blind staging (`git add .` or `git add -A`) so you never accidentally commit log files, `.env` secrets, or temporary memory dumps.

**Stage Subsystems Explicitly**:
```bash
# When updating backend subsystems:
git add backend/
git add "supporting files/rules/"
git add "supporting files/plans/"
git add "supporting files/testing/prototypes/"
git add "supporting files/testing/benchmarks/"
git add "supporting files/testing/unit/"

# When updating frontend subsystems:
git add frontend/
git add "supporting files/testing/mocks/"
```

#### What If You Accidentally Staged a Secret File?
If you accidentally staged a `.env` or sensitive file, remove it from staging immediately before committing:
```bash
git reset HEAD .env
# or if it was committed previously, un-track it:
git rm --cached .env
```

### Step 4: Write a Clear Commit Message
Use clean, descriptive commit messages:
```bash
git commit -m "feat(backend): add 5 consecutive 5xx error circuit breaker to async engine"
# or
git commit -m "feat(frontend): add Emergency Stop button and live latency chart to dashboard"
```

### Step 5: Push to Your Feature Branch
Push your branch to GitHub manually:
```bash
git push origin feature/<feature-name>
```

### Step 6: Merging into `main` via Pull Request
To prevent code breaking on `main`:
1. Never push directly to `main`.
2. Open a Pull Request (PR) on GitHub from your feature branch to `main`.
3. Review changes and verify tests pass.
4. Merge cleanly into `main`.

---

## 4. Protected Secrets & .gitignore Rules
Make sure your `.gitignore` file blocks the following items from ever entering GitHub:
* Environment secrets: `.env`, `.env.local`, `.env.*`
* Operating system files: `Thumbs.db`, `.DS_Store`, `desktop.ini`
* Python cache: `__pycache__/`, `*.pyc`
* Node dependencies: `node_modules/`
* Log and debug files: `*.log`, `debug.txt`
* Memory profiling dumps: `*.hprof`, `*.heapsnapshot`

---

## 5. Engineering & Continuation Discipline Rules

To ensure reliable, deterministic, and safe development across all human and AI contributors, the following engineering discipline rules must be upheld at all times:

1. **Inspect Before Coding**:
   - Always run `git status` and `git branch --show-current` to identify uncommitted changes.
   - Read all relevant `.md` rule, architecture, and testing specifications before altering any code or documentation.
2. **Continuation Audit (`COMPLETE / PARTIAL / MISSING / BROKEN`)**:
   - When picking up existing or in-progress features, systematically audit every requirement to verify its current state.
   - Preserve existing working code and modify only what is partial, missing, or broken.
3. **Locked Project Contracts**:
   - Never weaken, bypass, or invent competing formulas for locked project contracts (500 MB RAM scaling model, 48-hour auto-deactivation, SSRF defenses, 100-frame time sync, and 70% OS socket limits).
4. **Minimal File Changes**:
   - Touch only the files necessary for the specific assigned deliverable.
   - Never reformat unrelated files or refactor stable production components without explicit direction.
5. **Strict Git Safety**:
   - Automated commits and pushes by AI systems are strictly prohibited.
   - All Git stage, commit, and push actions remain under exclusive human control.
