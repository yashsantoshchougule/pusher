# GitHub Version Control & 2-Person Team Workflow

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

## 2. 2-Person Team Division & Git Branches

Pusher is built by a 2-person team. To prevent merge conflicts and stepping on each other's toes, the work is cleanly divided into two branches:

```
                                [ main Branch ]
                     (Production-ready, tested code only)
                                      ▲
                                      │ Pull Request Review & Merge
                  ┌───────────────────┴───────────────────┐
                  │                                       │
        [ branch: backend-dev ]                 [ branch: frontend-dev ]
              (Partner 1)                             (Partner 2)
  • backend/core/ (Frozen Engine Core)        • frontend/src/core_ui/ (Always-on Controls)
  • backend/plugins/ (Pluggable Features)     • frontend/src/features/ (Modular UI Cards)
  • backend/api/ (REST & WebSocket)           • supporting files/testing/mocks/ (Laptop 2)
  • supporting files/testing/prototypes/      • Live Speed & Latency Percentile Charts
  • supporting files/testing/benchmarks/      • Big Red Emergency Stop Button (<200ms)
  • SSRF Blocker & Safe DNS Pinning           • Verification Wizard Modal & Forms
```

> **Detailed Collaboration Rules**: See [`team_collaboration.md`](file:///c:/yash/projects/pusher/supporting%20files/rules/team_collaboration.md) for full folder ownership boundaries, API contracts, environment setup, and the 2-laptop Wi-Fi testing protocol.

### Team Member Responsibilities:

| Team Member | Git Branch | Primary Folders Owned | Key Tasks |
| :--- | :--- | :--- | :--- |
| **Partner 1** | `backend-dev` | • `backend/core/`<br>• `backend/plugins/`<br>• `backend/api/`<br>• `supporting files/testing/prototypes/`<br>• `supporting files/testing/benchmarks/`<br>• `supporting files/testing/unit/` | • Engine core (`socket_pool.py`, `stream_reader.py`, `orchestrator.py`)<br>• Scalable plugins (`traffic_modes/`, `breakers_and_detectors/`, `verifiers/`)<br>• Domain verification & safe DNS pinning<br>• 2-in-1 Pusher Guard generator & `X-Pusher-Bypass` injection<br>• Safety circuit breakers & RAM efficiency (<250MB) |
| **Partner 2** | `frontend-dev`| • `frontend/src/core_ui/`<br>• `frontend/src/features/`<br>• `supporting files/testing/mocks/` | • React + Tailwind UI layout (`core_ui/` & `features/`)<br>• Live charts (RPS, latency percentiles `p50`–`p99`)<br>• Big Red Emergency Stop button (`<200ms`)<br>• Verification wizard UI with 2-in-1 guard download modal<br>• Mock test servers for Laptop 2 |

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
- [ ] **Zero Full-Page Buffering**: Responses are streamed in small chunks and discarded.
- [ ] **Tests Pass**: Run your unit tests and mock server checks locally.

### Step 3: Explicitly Stage Your Files
Avoid blind staging (`git add .` or `git add -A`) so you never accidentally commit log files, `.env` secrets, or temporary memory dumps.

**For Partner 1 (Backend)**:
```bash
git add backend/
git add "supporting files/rules/"
git add "supporting files/testing/prototypes/"
git add "supporting files/testing/benchmarks/"
git add "supporting files/testing/unit/"
```

**For Partner 2 (Frontend)**:
```bash
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
# Partner 1 Example:
git commit -m "feat(backend): add 5 consecutive 5xx error circuit breaker to async engine"

# Partner 2 Example:
git commit -m "feat(frontend): add Emergency Stop button and live latency chart to dashboard"
```

### Step 5: Push to Your Team Branch
Push your branch to GitHub manually:
```bash
# Partner 1:
git push origin backend-dev

# Partner 2:
git push origin frontend-dev
```

### Step 6: Merging into `main` via Pull Request
To prevent code breaking on `main`:
1. Never push directly to `main`.
2. Open a Pull Request (PR) on GitHub from your branch to `main`.
3. The other team member reviews the code.
4. If there are merge conflicts in shared files (like `README.md` or `.env.example`), resolve them together in the GitHub PR web interface or locally before completing the merge.

---

## 4. Protected Secrets & .gitignore Rules
Make sure your `.gitignore` file blocks the following items from ever entering GitHub:
* Environment secrets: `.env`, `.env.local`, `.env.*`
* Operating system files: `Thumbs.db`, `.DS_Store`, `desktop.ini`
* Python cache: `__pycache__/`, `*.pyc`
* Node dependencies: `node_modules/`
* Log and debug files: `*.log`, `debug.txt`
* Memory profiling dumps: `*.hprof`, `*.heapsnapshot`
