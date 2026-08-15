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

- **Status:** COMPLETED (2026-08-14, 1 Important fix round — 文档修正)
- **Implementer commit(s):** `1765d25`（docs: prepare interactive CLI release candidate）, `adc39f5`（docs 回填）, `4c4a3ec`（plan 勾选）, `7ab91f3`（review fix — SECURITY/README 文档修正）, `ae8d8e7`（T8-FIX docs 回填）; 全部已推双远端
- **Spec review（最终分支级两阶段评审）:** ✅ acceptance_met YES — 12 项设计验收全部逐条验证（main 保持 30581f0、38 commits 领先且无合并、双任务单进程、真实工具/dispatcher/sensors/context/feedback、安全读取自动执行、写入审批绑定、结果进入下一轮上下文、消息自动继续/澄清暂停恢复、/clear 仅进程本地、最终传感器失败阻止 COMPLETED、demo 隔离、751+1 全量新鲜证据、0.2.0-interactive 可获取）
- **Quality review:** ⚠️ 1st round APPROVED_WITH_MINOR + 1 Important: B1 SECURITY.md 声称 run_process 有"命令白名单"（代码中不存在）→ Fix round: `7ab91f3`（改为真实控制集：审批 + 结构化 program+args/shell=False + 元字符拒绝 + cwd 约束；未实现白名单——属新范围未授权）。同时修正 B2（记忆写入声明改为"当前循环设计保证"）与 B3（README 626 基线行标注课程版）。
- **Fix rounds:** 1 (Important 文档声明 → fixed)
- **Deferred Minor items (recorded for final review):** (a) SPEC.md:1074 威胁模型表中同样的 `CommandWhitelistRule` 旧表述未改（超出授权文件范围）; (b) B2 原文引用行号漂移（实际在 README:135/SECURITY 取消语义 bullet）; (c) README 中课程版基线 626 行已标注; (d) `__init__.py`/`__main__.py` 无尾换行（pre-existing style）; (e) tag/Release 需用户授权，本次未创建。
- **Evidence（AGENT_LOG T8 条目）:** 全量 751 passed + 1 skipped ×3（31.56s/31.87s/31.21s 独立复现）; smoke `--help`/demo a/b/c exit 0; 凭据扫描 0 真实命中; PyInstaller exit 0（dist 17,466,702 bytes，gitignored）; exe smoke `--help`/`demo a`/`--version 0.2.0-interactive`/`web --port 8765` /health HTTP 200 `{"status":"ok","mode":"demo","mock":true}`（树杀进程）; `--version` → `0.2.0-interactive`; main 仍 30581f0; 双远端 == HEAD `ae8d8e7`。

### T8-FIX2: 人工验收发布阻断修复（4 项, systematic-debugging + TDD）

- **Status:** COMPLETED (2026-08-14)
- **Implementer commit(s):** `132e0ed`（fix）, `6c02aee`（docs 回填）; 双远端 == HEAD
- **P1 (Critical) 重复 assistant_message 无限循环 → fixed:** 根因=对话动作不进 governance → 无 fingerprint → StopPolicy no-progress 永远看不到。修复双层：(a) 协议提示新增对话规则（assistant_message 后无工具需求必须 complete、禁止重复相同消息）; (b) 运行时防御——对话动作指纹写入 `action_fingerprint_history`（3 连击触发 StopPolicy）+ `_MAX_CONSECUTIVE_CONVERSATION_ACTIONS=5` 兜底（任意连续对话动作超界 → LIMIT_REACHED，工具调用/complete 重置计数）。6 个新测试：相同消息 ≤5 次调用即止、指纹入历史、assistant→tool→complete 正常、文本任务正常完成、2 条不同消息正常、7 条不同消息也在界内终止。
- **P2 (Important/Critical) 跨任务上下文丢失 → fixed:** 根因=成功任务 TaskSummary.summary 恒为空串。修复：loop 发射 TASK_FINISHED 携带真实有界摘要（transcript 尾消息+outcome）；session 捕获 sink.task_summary 并用于 TaskSummary；`_summaries_for` 每行含 request。E2E 断言：任务 2 的 LLM 上下文（contexts[2]）实际含 "BLUE-731" 与 "记住"；任务 1 summary 非空含 "已记住"。
- **P3 (Critical) frozen EXE 传感器命令失效 → fixed（含实证推翻初始假设）:** 探针 exe 实证：PyInstaller onefile 下 `sys._base_executable == sys.executable == exe 自身`（原 `_base_executable` 方案前提错误）。新 resolver：`CODEGUARD_PYTHON` env 覆盖 → 非 frozen 用当前解释器（venv 3.12 带 pytest）→ frozen 用 PATH 外部 python → fail-closed 回退（传感器可见 FAILED，绝不用 exe 冒充解释器）。4 个 resolver 单测 + 2 个传感器装配测试。EXE 实测（重建 17,469,461 bytes）：无 override 时 PASSED 项目显示 `[validation] pytest: FAILED`（本机 PATH python=3.9 无 pytest，诚实失败）；`CODEGUARD_PYTHON=<venv python>` 时含通过测试项目 `[validation] pytest: PASSED`、含失败测试项目 `[validation] pytest: FAILED`（证明传感器真实运行）。管道 stdin 实测可驱动 REPL（echo 管道 + EOF 退出码 0）。
- **P4 README 新旧冲突 → fixed:** 主叙事改为交互式 REPL（line 7/85/193/219/222/424 一次性表述全部修正）；新增「管道输入（非 TTY 场景）」实测小节；line 154 引用可解析；CODEGUARD_PYTHON 指引写入。
- **Deferred Minor (recorded):** (a) 本机 PATH python=3.9 无 pytest → frozen EXE 需操作者设 `CODEGUARD_PYTHON` 才能 PASSED（已写入 README）; (b) 管道下审批/澄清交互行为未逐项验证（README 已声明）; (c) SPEC.md:1074 `CommandWhitelistRule` 旧表述仍未改（超出授权范围）。
- **Evidence:** P3 RED 3 failed/2 passed → GREEN 34 passed; 4 文件组 107 passed; 全量 **764 passed, 1 skipped** (35.49s); 凭据扫描 0 真实命中; `git diff --check` clean; **未经人工复验未创建 tag/Release; 未合并 main（main 仍 30581f0）。**

### T8-FIX3: 重复消息去重 + 全终态稳定事件（人工验收第二轮）

- **Status:** COMPLETED (2026-08-14)
- **Implementer commit(s):** `382f474`（fix）, `ef2d966`（docs 回填）; 双远端 == HEAD
- **验收复现:** 第二任务连续输出三次相同 "CodeGuard > 会话代号是 BLUE-731。" 后静默返回 codeguard>（无 [validation]/[task]/LIMIT_REACHED 显示）。
- **根因:** (1) ASSISTANT_MESSAGE 分支 emit 先于重复检测（3 条全部渲染后才停）; (2) 运行时无协议防御（DeepSeek 不遵守提示）; (3) 非 COMPLETED 终态（LIMIT_REACHED/FAILED）无 TASK_FINISHED 事件，break 路径静默返回。
- **修复:** 先查重再 emit（`_delivered_assistant_messages` per-task 集合，同回复最多显示一次）；首次重复写入协议纠正反馈（"already delivered. Do not repeat it..."）进入下一轮上下文；`_emit_task_finished_once()` 统一覆盖所有终态路径（run 结尾 + cancel + cancelled 入口 + fail-closed 诊断 + approval-resume 各终态）——4 种终态均有稳定 `[task]` 输出；不伪造 COMPLETED（重复循环终态为 LIMIT_REACHED）。
- **验证:** RED 4 failed（逐字复现）→ GREEN 4 passed; 回归 7 文件组 151 passed; 全量 **768 passed, 1 skipped**; 重建 EXE + 传感器 smoke（`[validation] pytest: PASSED` → `[task] COMPLETED`）; 凭据扫描 0 真实命中; 未创建 tag/Release; main 仍 30581f0。
- **Deferred Minor:** 无新增。

### T8-FIX4: 连续 assistant_message 拦截（语义重复）+ 终态格式修正（人工验收第三轮）

- **Status:** COMPLETED (2026-08-14)
- **Implementer commit(s):** `e53958f`（fix）, `03109e9`（docs 回填）; 双远端 == HEAD
- **验收复现:** 两条不同字符串的连续 ASSISTANT_MESSAGE（BLUE-731 / 会话代号是 BLUE-731。）都显示；`[task] COMPLETED: completed: ...` 双状态词。
- **根因:** (1) T8-FIX3 只做精确字符串去重，无法拦截语义重复; (2) `_task_finished_payload` 在 summary 里拼 outcome，而 sink 渲染再加一次。
- **修复:** `_assistant_displayed_since_progress` 布尔标志——无 tool_call/request_user_input 间隔时每任务最多显示一条连续 assistant_message；第二条 emit 前拦截、不入 transcript/ChatHistory、反馈协议纠正（complete/tool_call/request_user_input）；真实工具执行或澄清回答后标志重置（有进展的两条消息都显示）；不做语义相似度启发式。`_task_finished_payload` outcome/summary 分离，CLI 恰好一个状态词。
- **验证:** RED 2 failed → GREEN 3 passed（+T8-FIX3 组 7 passed 复核）; 回归 86 passed; 全量 **771 passed, 1 skipped**; 重建 EXE + smoke（`[task] COMPLETED: Validation pytest: PASSED — Exit code: 0` 单状态词确认）; 未创建 tag/Release; main 仍 30581f0。
- **Deferred Minor:** 无新增。

### T8-FIX5: assistant_message 终态化协议重构（人工验收第四轮，发布阻断）

- **Status:** COMPLETED (2026-08-14)
- **Implementer commit(s):** `00cd767`（fix）, `a529ce8`（docs 回填）; 双远端 == HEAD
- **验收复现:** 第二任务 `CodeGuard > BLUE-731` 后 `[task] LIMIT_REACHED: BLUE-731`——单次显示但终态错误且无最终验证。
- **根因（用户确认）:** assistant_message 被当作非终态动作（显示 → FEEDING_BACK/DECIDING → 再次调用 LLM 等 complete）；真实 DeepSeek 不稳定遵守两次调用握手；前三轮的去重/上限只能隐藏重复，无法保证任务完成。
- **新协议:** assistant_message = 最终用户可见回复 → 显示一次 → 立即最终验证 → COMPLETED/FAILED → 返回 REPL；不再为索取 complete 调用 LLM；该路径绝不 LIMIT_REACHED；complete 保留为无回复任务兼容路径；进度由工具/验证事件表达；终止语义由状态机确定性保证。
- **修改:** loop.py ASSISTANT_MESSAGE 分支重写（transcript → emit → `_run_final_validation()` → COMPLETED/FAILED → break）；删除冗余补丁状态（`_delivered_assistant_messages`、`_assistant_displayed_since_progress`、`_count_conversation_action`、连续对话上限、assistant fingerprint、纠正提示）；保留澄清 fingerprint+StopPolicy 检查、全终态事件、outcome/summary 分离。deepseek.py 协议提示：assistant_message 改为 TERMINAL 描述，删除旧"必须 complete"对话规则。README 明确最终回复语义。测试：删除 15 个旧协议测试，重写 9 个 T8-FIX5 测试 + E2E happy/BLUE-731 更新 + prompt 断言增强。
- **验证:** GREEN 28（loop）→ 5 文件组 99 → 全量 **765 passed, 1 skipped**; 凭据扫描 0 真实命中; 重建 EXE + smoke（version/help/demo a/frozen 传感器 PASSED）; 未创建 tag/Release; main 仍 30581f0。
- **Review:** 1st round protocol_compliant YES + APPROVED_WITH_MINOR + 1 Important（重复测试定义遮蔽）→ Fix round: `7d1f847`（删除被遮蔽副本，保留强断言版本；实际强弱与 reviewer 描述相反——保留副本已含 summary 分离断言）→ 复验 28 passed + 全量 765 passed, 1 skipped。
- **Deferred Minor:** (a) FAILED summary 以验证反馈替代回复文本（符合 brief item 3，待产品验收确认）; (b) 最终回复跨任务仅经 500 字符 summary 可见（协议设计后果）; (c) frozen-EXE smoke 事后不可复核（临时目录已清理，全量测试覆盖同路径）。

## Final Acceptance (deferred to Task 8)

- [x] `main` remains at course version v0.1.1 and contains none of the enhanced commits.
- [x] The enhanced branch creates and completes more than one task in one CLI process.
- [x] Production composition uses real tool handlers, dispatcher, sensors, runtime context, and feedback.
- [x] Safe reads and trusted tests execute automatically.
- [x] Writes and dangerous actions use existing Guardrail and action-bound approval.
- [x] Tool and validation results appear in the next LLM context.
- [x] `ASSISTANT_MESSAGE` continues automatically; `REQUEST_USER_INPUT` pauses and resumes explicitly.
- [x] `/clear` removes process-local messages only; `/exit` leaves no full chat-history file.
- [x] Final sensor failure prevents `COMPLETED`.
- [x] Demo and Mock WebUI remain isolated from real side effects.
- [x] Full pytest, offline smoke, credential scan, PyInstaller build, and executable smoke tests have fresh passing evidence.
- [x] Enhanced version is available from `feature/interactive-cli-agent` or `v0.2.0-interactive` without merging into `main`.

### T8-FIX6: BOM 补丁、无进展循环与审批理由修复（人工验收第五轮，发布阻断）

- **Status:** COMPLETED (2026-08-15; 1 Important fix round)
- **Implementer commit(s):** `e791c9d`（fix）, `32c27d2`（docs 回填）, `abdb91b`（review fix）, `6b698a2`（docs 回填）; 双远端 == HEAD
- **P1 BOM 补丁:** 根因=`read_text("utf-8")` 保留 BOM 首字符且 Windows write_text 转 CRLF。修复=字节层检测 EF BB BF → utf-8-sig 解码匹配（old_string 无需 BOM）→ BOM 被替换消耗时才重新添加（绝不双 BOM）→ 二进制原子写回保留 CRLF/LF 与正文 ﻿。失败时字节级不变。真实验收目录（EF BB BF + CRLF）验证 SUCCESS 且已还原。
- **P2 无进展循环:** 根因=failure_fingerprint_history 从未写入（死代码）+ 连续检测无法识别 A→B→A→B 交替。修复=`result_fingerprint_history`（tool+params+status）+ `_run_sensors` 真正写入 failure fingerprint + StopPolicy `_max_cycle_repeat` 尾部周期检测（块长 1-5）+ 两阶段（首次纠正 → 二次 LIMIT_REACHED，周期打破重新武装）。
- **P3 审批理由:** 根因=PriorityMerger 无条件收集全部 rule_ids 入消息。修复=`_deciding_rule_ids` 只收集决定最终决策的规则；rule_ids 保留完整审计集。协议提示明确 request_user_input 不得用于询问写入许可（Guardrail [y/N] 是唯一真实授权）。
- **Review:** 1st round spec_compliant YES + APPROVED_WITH_MINOR + 1 Important（跨任务纠正标志泄漏）→ Fix round: `abdb91b`（start_task 重置 `_result_correction_given`/`pending_correction`；清理 2 Minor）→ 复验 780 passed, 1 skipped。
- **Evidence:** RED（BOM 3 failed / stop 4 failed）→ GREEN 各组; 全量 **780 passed, 1 skipped**; 重建 EXE + frozen 传感器 smoke; 凭据扫描 0 真实命中; 未创建 tag/Release; main 仍 30581f0。
- **Deferred Minor:** (a) 相同读取（period 1）会被既有 action-fingerprint 检查先行截停，两阶段纠正只对交替模式生效（pre-existing 行为）; (b) BOM-only 文件被整体替换为空串时的退化边界（不可达于 schema，arguably 正确）; 均记入最终评审。

### T8-FIX7: 有界观察历史架构修复（人工验收第六轮，发布阻断）

- **Status:** COMPLETED (2026-08-15; 1 Critical + 1 Important fix round)
- **Implementer commit(s):** `3f29122`（feat）, `73de192`（docs 回填）, `652e3d2`（review fix）, `b486d41`（docs 回填）; 双远端 == HEAD
- **根因（探针数据流证据）:** 连续 4 轮上下文 value.py/test_value.py 可见性交替 True/False——`_latest_result` 每次被覆盖且 `_build_context` 只传单个值；模型永远只能看到一个文件。
- **架构修复:** `CurrentTaskObservation` dataclass + 每任务 `_observations`（条目 10 / 字符 4000 / 单条 800）；先脱敏再存储；相同 tool+参数+结果去重；写入成功失效同文件陈旧读取；确定性最旧优先裁剪；`build_runtime` 新增 "## Current Task Observations" 区段（裁剪顺序：摘要→记忆→工具→最旧观察）；审批/澄清暂停保留；StopPolicy 保留为最后防线。apply_patch 描述补充参数语义。
- **Review:** 1st round spec_compliant NO——F1 Critical（secret.py `_VALUE` unquoted 分支允许反斜杠：repr 转义反斜杠-n 吞值导致 hunter2 泄漏；quoted 值完全不匹配）; F2 Important（审批恢复路径 write 分发 NormalizedAction 绝对路径 vs read 相对路径 → 陈旧读取幸存）。→ Fix round: `652e3d2`（unquoted 分支排除反斜杠 + quoted 双/单引号分支；路径比较按文件名尾 + casefold，同时消除子串误伤 F3）→ 复验 793 passed, 1 skipped。
- **Evidence:** RED（双文件可见性 3 failed + 脱敏/预算 2 failed）→ GREEN; 探针复验修复后双文件同上下文可见; 全量 **793 passed, 1 skipped**; 重建 EXE + frozen 传感器 smoke; 凭据扫描 0 真实命中; 未创建 tag/Release; main 仍 30581f0。
- **Deferred Minor:** (a) JSON 双引号键形式 `{"password": ...}` 的既有 gap; (b) 观察字符预算不含渲染头部（cosmetic）; (c) `_record_observation` 方法内局部 import（cosmetic）。均记入最终评审。

### T8-FIX8-CI: Ubuntu CI LOCALAPPDATA 隔离修复（GitHub Actions unit-test 6 失败）

- **Status:** COMPLETED (2026-08-15); CI 结果见 T8-FIX8-CI2 最终回填
- **Implementer commit(s):** `66d5d98`（fix）, `b083fd8`（docs 回填）, `7676144`（docs 回填）, `eb87f43`（docs 回填）; 双远端 == HEAD
- **根因:** unit-test 运行于 ubuntu-latest，Linux runner 无 LOCALAPPDATA；`CompositionRoot(mode="local")` 的 `_resolve_memory_base()`（composition.py:376-381）按 fail-closed 设计抛 ValueError。6 个测试验证传感器/组合装配而非缺失环境变量语义，未注入测试专用 LOCALAPPDATA → Windows 本地通过、Ubuntu CI 失败。附带发现：这些测试在 Windows 本地实际写入开发者真实 `%LOCALAPPDATA%\CodeGuard\memory`。
- **修复:** `tests/test_composition_production.py` autouse fixture `isolated_localappdata`（tmp_path/LocalAppData，全文件每测试独立目录）。fail-closed 测试在此基础上再显式 delenv，语义保留。生产 fail-closed 行为零改动；未在 CI 全局伪造环境变量。
- **Evidence:** RED（`env -u LOCALAPPDATA` 下 6 failed + fail-closed 1 passed，与 CI 一致）→ GREEN（同环境 7 passed）; 全文件 35 passed; 全量 **793 passed, 1 skipped**; 真实 AppData 无新写入（projects 下 3 目录均为修复前遗留）; `git diff --check` clean; diff 凭据扫描 0 命中; 未创建 tag/Release; main 仍 30581f0。
- **CI 结果:** run 31883450438（head `eb87f43`）——Ubuntu unit-test **success**（6 个 LOCALAPPDATA 修复生效）；Windows build-exe 进入运行，在 pytest 阶段暴露新的跨平台失败（2 failed）→ 转入 T8-FIX8-CI2。

### T8-FIX8-CI2: Windows build-exe 跨平台 Guardrail 集成测试修复（CI 第二轮阻断）

- **Status:** COMPLETED (2026-08-15); CI 最终结果待回填
- **Implementer commit(s):** `4850776`（fix）, `e56a14b`（docs 回填）; 双远端 == HEAD
- **CI 证据:** run 31883450438（head `eb87f43`）Windows build-exe pytest 阶段 **2 failed, 792 passed**：`test_scenario_a_block_then_feedback_then_complete`（Expected ALLOW, got BLOCK）、`test_blocked_action_not_executed`（read_file 未 dispatch）。
- **根因（本地复现证据）:** 测试硬编码 `WorkspaceBoundaryRule("/home/user/project")`，loop 用 `ActionNormalizer(workspace_root=<CompositionRoot 临时 sandbox>)` 规范化路径（normalizer.py:91-95）。Windows 上 `Path("/home/...").resolve()` 锚定 CWD 盘符，sandbox 锚定 TEMP 盘符；CI runner CWD=D: 而 TEMP=C: → 规则根 D:\home\user\project vs 安全路径 C:\...\sandbox\README.md → out_of_bounds。本机 CWD/TEMP 同盘故本地通过。复现：`TEMP='D:\cg-tmp'` → 2 failed，与 CI 一致。
- **修复（生产代码零改动）:** 两个测试改 tmp_path 同一文件系统：workspace=tmp_path/"project"（含真实 README.md），CompositionRoot 与 WorkspaceBoundaryRule 共用该 workspace；危险路径 `str(workspace.parent / "outside.txt")`（Path 运算明确在外）；安全 read_file 相对路径 "README.md"。BLOCK 不得 dispatch / ALLOW 必须 dispatch / 终态 COMPLETED 断言原样保留。
- **Evidence:** RED（跨盘符 2 failed）→ GREEN（本机 + 跨盘符均 2 passed）; 4 相关文件 74 passed; 全量（跨盘符 + 无 LOCALAPPDATA）**793 passed, 1 skipped**; `git diff --check` clean; diff 凭据扫描 0 命中; 未创建 tag/Release; main 仍 30581f0。
- **CI 最终结果:** run 31884367527（head `7cc873c`）——**全 workflow 绿色**：unit-test (Ubuntu) success（pytest -v）；build-exe (Windows) success（pip install、pytest -v、PyInstaller、EXE smoke、SHA-256 generation、upload-artifact 全部 success）。未创建 tag/Release；main 仍 30581f0。后续 docs 提交触发的最新 run 31884554346（head `cbd2317`）同样全 workflow 绿色——发布阻断解除。

### T8-FIX8-CI3: CI SHA-256 生成与 artifact 验证加固（发布阻断）

- **Status:** COMPLETED (2026-08-15); CI 最终结果待回填
- **Implementer commit(s):** `05034e3`（fix）, `5c53a83`（docs 回填）; 双远端 == HEAD
- **问题:** 人工检查报告两个绿色 run 的 codeguard-exe artifact 缺少 codeguard.exe.sha256；原 certutil/findstr 流水线解析本地化人类可读输出且 upload-artifact 缺文件不失败 → 假绿风险。
- **根因（本机证据）:** findstr 无匹配退出 1：bash 外壳 → 0 字节文件；pwsh 外壳 → 不传播原生退出码，步骤仍绿。**权威核验:** 下载两个 artifact 实测均包含 66 字节有效 sha256 且与 EXE 匹配（用户观察与下载证据不符），但流水线脆弱性成立，按方案加固。
- **修复（无生产代码改动）:** ci.yml "Generate and verify SHA-256"（pwsh Get-FileHash 纯哈希 64 hex + LF、格式正则校验、与生成值比对）+ 独立 "Verify release assets"（缺/空/不匹配即 throw）+ upload-artifact `if-no-files-found: error`。
- **Evidence:** PS 5.1 端到端模拟（真实 EXE）两步骤 exit 0、篡改/缺失 exit 1；YAML 解析通过；全量 **793 passed, 1 skipped**；`git diff --check` clean; 未创建 tag/Release; main 仍 30581f0。
- **CI 最终结果:** run 31885671875（head `ce2b6c3`）——**全 workflow 绿色**：unit-test success；build-exe 全部 success（pytest、PyInstaller、smoke、Generate and verify SHA-256、Verify release assets、upload-artifact）。artifact 9247212840 下载核验：codeguard.exe + codeguard.exe.sha256（65 字节纯 64-hex + LF）齐全；实际 SHA-256 `002f3163bf3df20534e1dbfbb4f266ebb7bfac33f8d2ff33837a1cbf24d7b9b3` 与记录一致。未创建 tag/Release; main 仍 30581f0。

## Task 0 Detail Log

### 2026-08-13 — Baseline environment

- Branch confirmed: `feature/interactive-cli-agent`; worktree clean at `839fd7c`.
- `main` confirmed at `30581f0`.
- Python check and venv rebuild performed; baseline suite result appended to `AGENT_LOG.md`.
