# SDD Ledger — Interactive Coding-Agent CLI

> Plan: `docs/superpowers/plans/2026-08-13-interactive-cli-agent.md`
> Branch: `feature/interactive-cli-agent` (worktree `.worktrees/interactive-cli-agent`)
> `main` must stay at `30581f0` (v0.1.1, course version) — never merged into.
> Start: 2026-08-13
> Process: subagent-driven-development — one implementer per task (sequential), then spec-compliance review, then code-quality review; Critical/Important findings must enter fix + re-review loops.

## Baseline (Task 0)

| Item | Value |
|---|---|
| main commit | `30581f0` (v0.1.1) |
| HEAD at start | `839fd7c` (docs: plan interactive coding-agent CLI implementation) |
| Python | 3.12.x (via `py -3.12`) |
| Baseline suite | 626 passed, 1 skipped, 0 failed (recorded fresh in Task 0) |

## Task Tracking

### Task 0: Restore a Reproducible Python 3.12 Baseline

- [x] Step 1: Confirm isolated branch and broken baseline interpreter
- [x] Step 2: Install or select Python 3.12 with user approval
- [x] Step 3: Run the full baseline suite
- [x] Step 4: Verify no environment files are tracked
- **Status:** COMPLETED (no commit created)
- **Evidence:** baseline suite pass/skip counts, `git status` clean, `.venv` ignored

### Task 1: Define Conversation Actions and Harness Events

- [x] Step 1: Write failing action and state tests
- [x] Step 2: Run the targeted tests to verify RED (6 failed, 15 passed + collection error)
- [x] Step 3: Add the minimal action and state model
- [x] Step 4: Write failing event-contract tests (collection ERROR — module missing)
- [x] Step 5: Implement the event protocol
- [x] Step 6: Run GREEN and regressions (26 targeted + 32 related; full suite 637 passed, 1 skipped)
- [x] Step 7: Log and commit
- **Status:** COMPLETED (2026-08-13)
- **Implementer commit(s):** `f6134ac` (feat), `2d1d982` (docs-only AGENT_LOG hash backfill — noted deviation, spec reviewer judged acceptable)
- **Spec review:** ✅ compliant (independently verified all 10 requirement groups; 637 passed + 1 skipped reproduced)
- **Quality review:** ✅ APPROVED (no Critical/Important; 2 Minor: stale docstring in test_state.py:5, untested whitespace-only rejection — deferred polish, tracked)
- **Fix rounds:** 0
- **Deferred Minor items:** (a) `tests/test_state.py:5` docstring mentions nonexistent FINALIZING; (b) add parametrized whitespace-only parser rejection test. Tracked for opportunistic fix when Task 2+ touches these files.

### Task 2: Build Bounded Runtime Context and Process-Local History

- **Status:** PENDING
- **Implementer commit(s):**
- **Spec review:** PENDING
- **Quality review:** PENDING
- **Fix rounds:**

### Task 3: Wire Real Tools, Dispatcher, and Sensors in the Composition Root

- **Status:** PENDING
- **Implementer commit(s):**
- **Spec review:** PENDING
- **Quality review:** PENDING
- **Fix rounds:**

### Task 4: Feed Tasks, Tool Results, and Validation Back into AgentLoop

- **Status:** PENDING
- **Implementer commit(s):**
- **Spec review:** PENDING
- **Quality review:** PENDING
- **Fix rounds:**

### Task 5: Implement ChatSession and CLI Event Rendering

- **Status:** PENDING
- **Implementer commit(s):**
- **Spec review:** PENDING
- **Quality review:** PENDING
- **Fix rounds:**

### Task 6: Update DeepSeek Protocol and CLI Metadata

- **Status:** PENDING
- **Implementer commit(s):**
- **Spec review:** PENDING
- **Quality review:** PENDING
- **Fix rounds:**

### Task 7: Deterministic End-to-End Interactive Coding Test

- **Status:** PENDING
- **Implementer commit(s):**
- **Spec review:** PENDING
- **Quality review:** PENDING
- **Fix rounds:**

### Task 8: Documentation, Full Verification, and Enhanced Release Candidate

- **Status:** PENDING
- **Implementer commit(s):**
- **Spec review:** PENDING
- **Quality review:** PENDING
- **Fix rounds:**

## Final Acceptance (deferred to Task 8)

- [ ] `main` remains at course version v0.1.1 and contains none of the enhanced commits.
- [ ] The enhanced branch creates and completes more than one task in one CLI process.
- [ ] Production composition uses real tool handlers, dispatcher, sensors, runtime context, and feedback.
- [ ] Safe reads and trusted tests execute automatically.
- [ ] Writes and dangerous actions use existing Guardrail and action-bound approval.
- [ ] Tool and validation results appear in the next LLM context.
- [ ] `ASSISTANT_MESSAGE` continues automatically; `REQUEST_USER_INPUT` pauses and resumes explicitly.
- [ ] `/clear` removes process-local messages only; `/exit` leaves no full chat-history file.
- [ ] Final sensor failure prevents `COMPLETED`.
- [ ] Demo and Mock WebUI remain isolated from real side effects.
- [ ] Full pytest, offline smoke, credential scan, PyInstaller build, and executable smoke tests have fresh passing evidence.
- [ ] Enhanced version is available from `feature/interactive-cli-agent` or `v0.2.0-interactive` without merging into `main`.

## Task 0 Detail Log

### 2026-08-13 — Baseline environment

- Branch confirmed: `feature/interactive-cli-agent`; worktree clean at `839fd7c`.
- `main` confirmed at `30581f0`.
- Python check and venv rebuild performed; baseline suite result appended to `AGENT_LOG.md`.
