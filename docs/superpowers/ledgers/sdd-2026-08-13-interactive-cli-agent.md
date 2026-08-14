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

- **Status:** COMPLETED (2026-08-14, resumed after abnormal shutdown on 2026-08-13; 1 fix round, re-reviewed ✅ APPROVED_WITH_MINOR)
- **Implementer commit(s):** `496cc78`（`fix: wire production tools and validation sensors`）, `1d2dc81`（docs 回填）, `55bcaba`（review fix round 1）
- **Spec review:** ❌ 1st round (merge reviewer, single report): **Critical** — local-mode sensor command duplicated interpreter (`[python, python, -m, pytest, -q]`) so REQUIRED pytest sensor could never PASS → local mode could never reach COMPLETED; **Important** — legacy dual wiring preserved incomplete schemas (write_file path-only/ALLOW, apply_patch `patch` param) contrary to brief R3; **Important** — run_process schema `timeout maximum 300` not enforced anywhere. → Fix round: `55bcaba` (drop duplicated interpreter from `_VALIDATION_TOOL_DEFS` args; remove `full_governance` dual wiring — one complete-schema wiring for every mode, ToolRiskRule always registered, legacy tests updated with content params + two feedback-scope tests override write risk to ALLOW; SchemaValidator enforces integer/array types + minimum/maximum bounds). Full suite after fixes: 689 passed, 1 skipped.
- **Fix re-review:** ✅ Spec compliant (all 7 requirements verified; re-verification group 154 passed; full suite 689 passed, 1 skipped reproduced; demo loop verified live: tool_dispatcher None, sensor_runner None, required_sensors []) + quality APPROVED_WITH_MINOR (no new Critical/Important from fixes)
- **Fix rounds:** 1 (Critical + 2 Important → fixed → re-reviewed ✅)
- **Deferred Minor items (recorded for final review):** (a) ToolRiskRule returns ALLOW (not a non-verdict) for non-TOOL_CALL kinds, polluting rule_ids on conversation actions (rules.py:149-151); (b) `_register_standard_tools` silently swallows duplicate-registration ValueError (composition.py:265-272); (c) run_lint/run_typecheck tools always registered but their sensors only when `importlib.util.find_spec` succeeds — tool-vs-sensor asymmetry if ruff/mypy absent (fail-safe); (d) test-local `write_file.default_risk = "ALLOW"` overrides in test_integration_guardrail_feedback.py:365-367, 518-520 (commented, feedback-loop-scope, deliberate); (e) event_sink injection is Task 4 prep (benign extra scope).
- **Resume note:** 电脑于 Task 3 执行期间异常关机；工作树未提交修改（7 改 + 2 新建）视为恢复现场，未 reset/restore/覆盖。对照 brief 核查后仅补齐 demo 隔离缺口（TDD：新增 `test_demo_avoids_real_dispatcher_and_sensors`，修复 `_wire_common` 使 demo 不创建真实 dispatcher）。全量 686 passed, 1 skipped（pre-review）。

### Task 4: Feed Tasks, Tool Results, and Validation Back into AgentLoop

- **Status:** COMPLETED (2026-08-14, implementer 中断于 TDD RED 阶段后恢复补齐实现; 1 Important fix round)
- **Implementer commit(s):** `d37005c`（feat）, `2b4eb30`（docs 回填）, `f296291`（review fix）, `73e5eda`（T4-FIX docs 回填）
- **Spec review:** ✅ 1st round compliant（8 项全部满足，证据与实现一致；全量 698 passed, 1 skipped 复现）
- **Quality review:** ⚠️ 1st round APPROVED_WITH_MINOR + 1 Important：F1 approval-resume 路径不区分工具失败（无 failure 标记且被传感器反馈覆盖）→ Fix round: `f296291`（抽取 `_dispatch_tool` 共享两路径；`_run_sensors` 追加而非覆盖工具结果；RED 1 failed → GREEN 29 → 回归 61 → 全量 699 passed, 1 skipped）
- **Fix rounds:** 1 (Important → fixed → 修复已在同轮验证；T4-FIX AGENT_LOG 条目)
- **Deferred Minor items (recorded for final review):** (a) F2: ASSISTANT_MESSAGE/USER_INPUT_REQUESTED 事件 payload 未截断（上下文本身有界，仅影响 sink 渲染）; (b) F3: approval REJECTED/TIMEOUT 转 CANCELLED 未发射 TASK_FINISHED（与 cancel() 不一致，pre-existing 路径）; (c) F4: demo-mode loop 因 dispatcher/sensor_runner 为 None 导致 `start_task` 恒 FAILED（fail-closed 符合 brief，待 Task 5/8 决策）; (d) F5: `_validate_production_wiring` 若 redactor 本身缺失则诊断不脱敏（组件名非机密，影响极低）; (e) F6: cancelled 后 `resume_with_user_input` 抛 ValueError 而非返回 CANCELLED 结果（尚无 CLI 调用方）; (f) brief item 4 "parser error" 反馈未接线——loop 内无解析路径（解析错误在 adapter 层，属 Task 6 范畴）。
- **Resume note:** implementer 子代理在切换模型时被中断，现场保留了 RED 测试（9 个新测试，`start_task` 缺失）与 3 个未提交文件（mock.py received_contexts、composition.py project_id 注入、2 个测试文件）。恢复后未重制 RED，直接补齐 loop.py 实现 → GREEN 27 passed → 回归 60 passed → 全量 698 passed, 1 skipped。

### Task 5: Implement ChatSession and CLI Event Rendering

- **Status:** COMPLETED (2026-08-14)
- **Implementer commit(s):** `c3877d0`（feat）, `13c0d45`（docs 回填）
- **Spec review:** ✅ compliant（9 项全部满足；66 passed 目标组 + 44 passed sanity 复现；RED = 1 collection ImportError）
- **Quality review:** ✅ APPROVED_WITH_MINOR（无 Critical/Important）
- **Fix rounds:** 0
- **Deferred Minor items (recorded for final review):** (1) 纯空白 ASSISTANT_MESSAGE 会使 `history.add_message` 抛 ValueError 崩掉 REPL（session.py:297 需 strip/guard）; (2) `CodeGuard asks:` 提示与 approval 提示字段（target/reason）绕过 sink 500 字符截断（session.py:327-336, 375）; (3) `/status` 打印 provider dict 值无界（session.py:233）; (4) `chat_command` 用 "cli-session" 而 ChatSession 自生成 uuid，事件/历史 ID 不一致（无绑定 bug）; (5) 成功任务的 TaskSummary.summary 为空串（loop TASK_FINISHED payload 仅 {"outcome"}，数据源薄）; (6) 非 BLOCK 的 FAILED 终态无任何终端渲染（历史有记录但用户看不到）; (7) 死参数（`_handle_user_input` 的 history/request、`_handle_approval` 的 history）与无注入 history 时 `/clear` 提示语误导。
- **Implementer concerns (verified):** (a) `chat_command` 急切创建 loop 使缺 key 在提示前 fail fast——符合既有测试断言，lazy factory 在 session 测试中充分覆盖; (b) TaskSummary 占位可接受; (c) 用户输入路径 strip 保护确认，唯一崩溃路径在 assistant 侧（Minor 1）。

### Task 6: Update DeepSeek Protocol and CLI Metadata

- **Status:** COMPLETED (2026-08-14, 1 Important fix round)
- **Implementer commit(s):** `e5faebf`（feat）, `c6a8356`（docs 回填）, `6167ea1`（review fix）, `f3cb991`（T6-FIX docs 回填）
- **Spec review:** ✅ compliant（5 项全部满足；43 passed 复现；RED 7 failed/15 passed）
- **Quality review:** ⚠️ 1st round APPROVED_WITH_MINOR + 2 Important: (1) redactor `\b(sk-)\w+` 在连字符处截断，DeepSeek 连字符 key 尾部泄漏（`sk-***-secret-tail` 可见）; (2) `raise ValueError(...) from e` 使 `__cause__` 保留未脱敏原始 provider 文本，且 strict-mode ValueError 会以 traceback 形式杀死交互 REPL。→ Fix round: `6167ea1`（redactor 模式改为 `\b(sk-)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*` 整段匹配；deepseek 去掉 `from e`；ChatSession `_run_task` 捕获 ValueError 打印 `[error]` 回到 REPL；RED 3 failed → GREEN 62 → 回归 114 passed）
- **Fix rounds:** 1 (2 Important → fixed → T6-FIX AGENT_LOG 条目)
- **Deferred Minor items (recorded for final review):** (a) 网络错误消息未脱敏（deepseek.py `Network error ... {e}` 可能含 URL/凭据，pre-existing）; (b) 脱敏测试应断言 `__cause__`/完整 traceback 安全; (c) 新增 redactor 可注入参数为 fine; (d) test_scaffold.py 文件缺尾换行（cosmetic）。

### Task 7: Deterministic End-to-End Interactive Coding Test

- **Status:** COMPLETED (2026-08-14; zero production changes — Tasks 3-6 集成已正确)
- **Implementer commit(s):** `f7a40cf`（test）, `692bf8b`（docs 回填）; 已按 push policy 推送双远端（origin + github 均 692bf8b）
- **Spec review:** ✅ compliant（6 项全部满足；RED 3 failed/7 passed 根因=模块级 assert 不被 pytest 收集 → exit 5 → sensor FAILED，测试侧修复未削弱断言；E2E 10 passed + 安全组 85 passed + 全量 751 passed, 1 skipped 复现）
- **Quality review:** ✅ APPROVED_WITH_MINOR（无 Critical/Important）
- **Fix rounds:** 0
- **Key decisions (documented in test docstring):** (1) scripted 响应用 Action 对象（loop 消费 next_action 而非 raw JSON）；(2) 真实 pytest 传感器每轮运行，微型临时项目必须用 `test_*` 函数；(3) "重复非法 JSON → LIMIT_REACHED" 采用治理失败路径（4× 相同工作区逃逸 write → recoverable BLOCK 同指纹 → 真实 StopPolicy no-progress 状态机）；(4) 失败必需最终传感器用测试级 `objective_verifier.required_sensors = ["pytest"]` 装配（同类于 ALLOW 覆盖惯例）；(5) demo 隔离为最强证明（LLM 调用前 fail closed、文件未创建、received_contexts == []）；(6) /clear 与结构化记忆用 loop 自身 memory_store/project_id 验证。
- **Deferred Minor items (recorded for final review):** (1) E2E 断言触及 `loop._feedback_results`/`state.action_fingerprint_history` 私有状态（考虑改断言渲染输出）；(2) test (f) 可直接断言 `objective_verifier.verify()` 返回 False 以隔离 verifier 阻断与 no-progress 终止；(3) test (g) 记忆记录为测试植入而非任务产出；(4) RED 状态仅存于 AGENT_LOG，无法从提交树复现（协议已记录确切失败）。

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
