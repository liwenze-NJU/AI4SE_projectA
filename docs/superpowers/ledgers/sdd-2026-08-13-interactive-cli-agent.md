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

- [x] Step 1: Write failing process-local history tests (collection ERROR — module missing)
- [x] Step 2: Implement bounded history
- [x] Step 3: Write failing runtime-context tests (TypeError: no-args)
- [x] Step 4: Run runtime-context tests to verify RED
- [x] Step 5: Implement `build_runtime` without breaking legacy `build`
- [x] Step 6: Run GREEN and regressions (15 targeted; full suite 647 passed, 1 skipped)
- [x] Step 7: Log and commit
- **Status:** COMPLETED (2026-08-13) — after 1 Critical fix round
- **Implementer commit(s):** `5b022fd` (feat), `3325847` (docs backfill), `fd6c898` (fix), `d6a9371` (docs backfill)
- **Spec review:** ❌ 1st round found **Critical**: infinite loop in `build_runtime` (context.py tool-halving loop never terminates when mandatory fields exceed max_chars with tools present — `len("")//2 == 0`; ValueError path unreachable). Reproduced (exit 124 hang). → Fix round: `fd6c898` (halve if len>1 else del; 2 regression tests; T2-FIX AGENT_LOG entry).
- **Fix re-review:** ✅ Spec compliant + quality APPROVED (termination proven in all probes incl. max_chars=1, multi-tool, randomized sweep; len<=max_chars invariant held; 649 passed + 1 skipped reproduced)
- **Fix rounds:** 1 (Critical → fixed → re-reviewed ✅)
- **Deferred Minor items (recorded for final review):** (a) redactor re-applied to tool strings per halving iteration (efficiency, pre-existing pattern); (b) `_is_over` re-assembles context per iteration (O(n) per step, pre-existing); (c) Task 1 leftovers: stale docstring test_state.py:5, whitespace-only rejection untested.

## Process Change — Risk-Tiered Verification (user directive, 2026-08-13, from Task 3 onward)

1. TDD still mandatory per task (targeted RED → GREEN).
2. Normal tasks run targeted + related-module regressions only (no full 600+ suite per task).
3. ONE reviewer per task, reporting BOTH spec-compliance and code-quality/security verdicts in one report.
4. Reviewer reads only the task brief, implementer report, and diff package — not full PLAN/SPEC/AGENT_LOG/repo history.
5. Risk-tiered intensity: Task 3 HIGH (real tools/Guardrail/Shell/memory/Mock isolation; full suite after); Task 4 HIGHEST (full spec/security/state-machine review; full suite); Task 5 MEDIUM (targeted + CLI regressions); Task 6 MEDIUM (DeepSeek protocol + error handling); Task 7 HIGHEST (E2E + security; full suite); Task 8 final branch-wide review, full suite, credential scan, build, smoke.
6. Model tiers: Task 3, 4, 7 and final branch review use Pro (opus); mechanical implementations/small fixes and Task 5/6 ordinary reviews prefer Flash (sonnet/haiku).
7. Minor issues → ledger, judged at final review; only spec non-compliance, Critical, or Important enter the fix loop.
8. Reviewer stalled >12 min without new output → check status; if stuck, interrupt and re-dispatch a lean reviewer.
9. Hard requirements unchanged: TDD, Guardrail/approval safety, Demo/Mock isolation, COMPLETED only after final validation, Task 8 full verification.
10. No pausing between tasks for permission.

## Task Tracking (revised from here)

### Task 3: Wire Real Tools, Dispatcher, and Sensors in the Composition Root

- **Status:** COMPLETED (2026-08-14, resumed after abnormal shutdown on 2026-08-13)
- **Implementer commit(s):** `T3-COMMIT`（提交后回填）
- **Spec review:** PENDING（合并 reviewer 双评审，见下方条目）
- **Quality review:** PENDING
- **Fix rounds:** 0
- **Resume note:** 电脑于 Task 3 执行期间异常关机；工作树未提交修改（7 改 + 2 新建）视为恢复现场，未 reset/restore/覆盖。对照 brief 核查后仅补齐 demo 隔离缺口（TDD：新增 `test_demo_avoids_real_dispatcher_and_sensors`，修复 `_wire_common` 使 demo 不创建真实 dispatcher）。全量 686 passed, 1 skipped。

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
