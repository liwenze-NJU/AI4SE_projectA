# Shared Two-Version README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace both branch READMEs with one byte-identical, neutral guide that introduces, obtains, explains, and validates the course and interactive versions.

**Architecture:** Author one canonical README in the `feature/interactive-cli-agent` worktree, validate its facts and examples, then apply that exact content to the `main` worktree. Keep implementation histories isolated: only `README.md` is shared between branches, while the design and plan records remain on the feature branch.

**Tech Stack:** Markdown, Git worktrees, PowerShell, GitHub Releases, Windows CLI/EXE

## Global Constraints

- `main` remains the course implementation at version `0.1.1`; no interactive implementation commits may be merged into it.
- `feature/interactive-cli-agent` remains the enhanced implementation at version `0.2.0-interactive`.
- Both `README.md` files must be byte-identical and use neutral, branch-independent wording.
- The shared README must distinguish one-shot course `chat` behavior from the enhanced REPL behavior.
- The enhanced Release tag and URL are `v0.2.0-interactive` and `https://github.com/liwenze-NJU/AI4SE_projectA/releases/tag/v0.2.0-interactive`.
- Do not expose API keys, private values, local usernames, or absolute local paths.
- Do not modify implementation code, tests, SPEC, PLAN, AGENT_LOG, SECURITY, or REFLECTION as part of this README delivery.
- Do not create or publish the enhanced Release until the final README commit is pushed and its CI is green.

---

### Task 1: Author and validate the canonical shared README

**Files:**
- Modify: `README.md` in `C:\Users\32197\Desktop\AI4SE_final_projectA\.worktrees\interactive-cli-agent`
- Reference: `docs/superpowers/specs/2026-08-15-shared-two-version-readme-design.md`

**Interfaces:**
- Consumes: verified CLI commands, branch names, version strings, acceptance observations, and the approved design specification.
- Produces: the canonical README content that Task 2 copies byte-for-byte into `main`.

- [ ] **Step 1: Replace the opening with a neutral two-version entry point**

  The opening must contain this information before detailed feature documentation:

  ```text
  Repository: https://github.com/liwenze-NJU/AI4SE_projectA
  Course version: main / 0.1.1
  Interactive version: feature/interactive-cli-agent / 0.2.0-interactive
  Isolation statement: the enhanced implementation has not been merged into main
  ```

  Include direct links to both branches, `v0.1.1`, and the planned `v0.2.0-interactive` Release URL.

- [ ] **Step 2: Write independent feature and acceptance sections for the course version**

  Include:

  ```text
  one-shot Harness session
  explicit state machine
  Guardrail and approval
  sensor/test feedback loop
  demo a/b/c
  local Mock WebUI and /health
  version/help/config checks
  source test instructions
  ```

  State explicitly that course-version `chat` is not a persistent REPL.

- [ ] **Step 3: Write independent feature and acceptance sections for the enhanced version**

  Include:

  ```text
  persistent chat REPL
  DeepSeek local mode and Keyring credentials
  read/search/patch/test/process tools
  per-action approval and workspace boundary
  clarification, cancel, summaries, and final validation
  secret redaction
  CODEGUARD_PYTHON for frozen-EXE pytest execution
  known limitations
  ```

  The manual acceptance sequence must cover EXE/SHA verification, built-in commands, cross-task context, BOM multi-file patching, approval rejection and approval success, workspace escape blocking, redaction, structured `run_process`, demos, WebUI, and `/health`.

- [ ] **Step 4: Preserve and consolidate shared technical documentation**

  Retain concise sections for:

  ```text
  Harness state machine and modules
  source installation and pytest
  PyInstaller build and SHA-256 generation
  directory structure
  security boundaries
  CI and Release delivery
  third-party dependencies
  course document index and submission notes
  ```

  Replace fixed test totals with “see the latest green CI and AGENT_LOG” so the shared README does not become stale after future test additions.

- [ ] **Step 5: Perform content checks**

  Run from the feature worktree:

  ```powershell
  $unfinished = ('TO' + 'DO') + '|' + ('T' + 'BD')
  Select-String -Path .\README.md -Pattern "$unfinished|<repo-url>|C:\\Users\\|BLUE-731|FAKE-CANARY" -CaseSensitive:$false
  git diff --check -- README.md
  ```

  Expected: no sensitive/private/placeholder matches and no whitespace errors. Legitimate Markdown angle-bracket URLs must not be treated as placeholders.

- [ ] **Step 6: Review the README diff**

  Run:

  ```powershell
  git diff -- README.md
  ```

  Confirm every branch-specific behavior is placed under the correct version heading and no sentence depends on which branch currently displays the file.

- [ ] **Step 7: Commit the canonical README on the feature branch**

  ```powershell
  git add README.md
  git commit -m "docs: publish shared two-version README"
  ```

### Task 2: Synchronize the exact README to main without merging code

**Files:**
- Reference: `README.md` in `C:\Users\32197\Desktop\AI4SE_final_projectA\.worktrees\interactive-cli-agent`
- Modify: `README.md` in `C:\Users\32197\Desktop\AI4SE_final_projectA`

**Interfaces:**
- Consumes: the validated canonical README committed by Task 1.
- Produces: a byte-identical README on `main`, with no other main-branch changes.

- [ ] **Step 1: Verify both worktrees are on the intended branches**

  Run:

  ```powershell
  git -C C:\Users\32197\Desktop\AI4SE_final_projectA branch --show-current
  git -C C:\Users\32197\Desktop\AI4SE_final_projectA\.worktrees\interactive-cli-agent branch --show-current
  ```

  Expected:

  ```text
  main
  feature/interactive-cli-agent
  ```

- [ ] **Step 2: Apply the canonical content to the main README**

  Use `apply_patch` to replace the main worktree's `README.md` with the exact canonical content from Task 1. Do not use merge, cherry-pick, checkout, or copy operations that could transfer other feature-branch files.

- [ ] **Step 3: Verify byte identity**

  Run:

  ```powershell
  Get-FileHash C:\Users\32197\Desktop\AI4SE_final_projectA\README.md -Algorithm SHA256
  Get-FileHash C:\Users\32197\Desktop\AI4SE_final_projectA\.worktrees\interactive-cli-agent\README.md -Algorithm SHA256
  ```

  Expected: both SHA-256 values are identical.

- [ ] **Step 4: Verify main contains no implementation changes**

  Run from the main worktree:

  ```powershell
  git status --short
  git diff --check
  git diff --name-only
  ```

  Expected before commit: only `README.md` appears and `git diff --check` is clean.

- [ ] **Step 5: Commit the shared README on main**

  ```powershell
  git add README.md
  git commit -m "docs: document both project versions"
  ```

### Task 3: Push, verify CI, and hand off Release creation

**Files:**
- Verify: `.github/workflows/ci.yml`
- Verify: `README.md` on both remote branches

**Interfaces:**
- Consumes: the two README commits from Tasks 1 and 2.
- Produces: remote branches with identical documentation and a green enhanced commit ready to tag as `v0.2.0-interactive`.

- [ ] **Step 1: Push each branch without merging them**

  Push `main` from the main worktree and `feature/interactive-cli-agent` from the feature worktree to the configured GitHub and course remotes. Do not use `--force`.

- [ ] **Step 2: Confirm remote branch heads**

  Run:

  ```powershell
  git rev-parse main
  git rev-parse feature/interactive-cli-agent
  git ls-remote github refs/heads/main refs/heads/feature/interactive-cli-agent
  ```

  Expected: remote branch hashes match the corresponding local branch hashes.

- [ ] **Step 3: Confirm the enhanced branch's newest GitHub Actions run is green**

  Verify both the unit-test and Windows build/EXE jobs succeed for the exact feature-branch README commit. Download the artifact and confirm it contains:

  ```text
  codeguard.exe
  codeguard.exe.sha256
  ```

- [ ] **Step 4: Reconfirm README identity at the committed revisions**

  Materialize or inspect `main:README.md` and `feature/interactive-cli-agent:README.md`, hash both byte streams, and confirm equality. A working-tree-only equality check is insufficient after pushing.

- [ ] **Step 5: Hand off Release creation**

  Create the enhanced GitHub Release only after Step 3 is green:

  ```text
  Tag: v0.2.0-interactive
  Target: the exact green feature/interactive-cli-agent commit
  Title: CodeGuard v0.2.0-interactive — Interactive CLI Agent
  Assets: codeguard.exe and codeguard.exe.sha256 from that exact CI run
  ```

  Verify the published URL is `https://github.com/liwenze-NJU/AI4SE_projectA/releases/tag/v0.2.0-interactive`.
