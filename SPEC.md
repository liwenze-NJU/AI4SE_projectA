# SPEC.md — CodeGuard Harness 设计规约

> 版本：1.1.4
> 日期：2026-08-04
> 状态：已确认

---

## 1. 问题陈述

### 1.1 背景

Agent = LLM + Harness。LLM 相当于 CPU，只负责"决定下一步做什么"这一行任务决策；其余都是工程——组织上下文、调用 LLM、解析动作、分发执行、治理拦截、反馈回灌、记忆固化。一个可靠的 Coding Agent 必须建立在由代码实现的工程机制之上，而非仅靠提示词约束 LLM 行为。

### 1.2 要解决的问题

当前 AI 编码助手（如 Claude Code、GitHub Copilot）是闭源的全栈 harness，用户无法了解其治理、反馈和记忆机制的工作方式。本项目旨在构建一个**开源、可审计、可测试**的 Coding Agent Harness 内核，展示 Agent 系统的工程本质。

### 1.3 目标用户

需要在本地受控环境中使用 AI 辅助编码的开发者，要求在危险操作执行前有人工审批、测试结果可客观反馈并驱动自我修正。

### 1.4 为什么值得做

本项目是 AI4SE 课程的命题实践：当 LLM 能完成大部分"思考"时，工程师的价值落在 harness 这层工程（治理、反馈、安全、分发）。通过从零构建一个 harness，对 Agent 工程方法论形成第一手的批判性理解。

---

## 2. 用户故事

以下故事遵循 INVEST 原则（Independent, Negotiable, Valuable, Estimable, Small, Testable）：

1. **US-1 治理拦截**：作为开发者，当我让 Agent 执行危险命令（如删除系统目录）时，Harness 在代码执行前拦截并阻止，不依赖 LLM 自觉遵守安全提示。

2. **US-2 人工审批**：作为开发者，当 Agent 请求删除工作区内文件或安装依赖时，Harness 暂停执行并要求我明确批准或拒绝，且批准仅针对该次具体操作。

3. **US-3 测试反馈闭环**：作为开发者，当 Agent 修改代码后测试失败时，Harness 自动运行测试、解析失败原因、将结构化反馈回灌给 LLM，驱动 Agent 自我修正。

4. **US-4 凭据安全存储**：作为开发者，我通过隐藏命令安全录入 DeepSeek API Key，Key 经 Windows Credential Manager 加密存储，不出现在配置文件、日志或 Git 历史中。

5. **US-5 跨会话记忆**：作为开发者，当我重新启动 Agent 时，它能记住之前会话中确认的项目约定和关键决策，无需重复说明。

6. **US-6 受限工作区**：作为开发者，Agent 只能在指定的项目目录内读写文件，任何越界访问被代码层阻止。

7. **US-7 机制演示**：作为评估者，我可以在 WebUI 上选择预设场景，观察治理拦截、审批流程和反馈闭环的确定性执行过程，无需配置真实 LLM。

8. **US-8 一键测试**：作为维护者，我运行 `pytest` 即可验证 Harness 全部核心机制，测试使用 Mock LLM，不依赖网络或真实 API Key。

---

## 3. 功能规约

### 3.1 Agent 主循环（FC-1）

**状态机**：
```
INITIALIZING → BUILDING_CONTEXT → DECIDING → GOVERNING
  → (AWAITING_APPROVAL) → EXECUTING
  → INTERMEDIATE_VALIDATION* → FEEDING_BACK → DECIDING (循环)
  → LLM 返回 COMPLETE_REQUEST → FINAL_VALIDATION (含 ObjectiveVerifier)
  → 全部通过 → COMPLETED
  → 验证失败 → FEEDING_BACK → DECIDING (≤ max_repair)
  → COMPLETED / FAILED / CANCELLED / LIMIT_REACHED → FINALIZING
```

> * 只读操作（read_file/list_directory 等）直接进入 FEEDING_BACK，不触发 INTERMEDIATE_VALIDATION。

**输入**：用户任务描述、配置、项目文件

**行为**：
- 启动装配阶段加载配置、选择 Composition Root、装配依赖、检查安全 backend
- 主循环依次执行状态转换，每个状态由确定性代码驱动
- **INTERMEDIATE_VALIDATION**：普通工具执行后的验证，通过后进入 FEEDING_BACK → DECIDING，不能直接完成任务
- **FINAL_VALIDATION**：仅由 COMPLETE_REQUEST 触发，运行必需传感器和 ObjectiveVerifier；全部通过 → COMPLETED；否则 → FEEDING_BACK
- 超出重试或步数限制 → LIMIT_REACHED
- 停机后执行 FINALIZING（固化记忆、关闭 trace、清理资源）

**输出**：SessionResult（包含最终状态、执行摘要、Trace 记录）

**边界条件**：
- LLM 返回 COMPLETE_REQUEST 表示请求结束，但不等同于任务成功
- 只读任务也必须由代码定义 ObjectiveVerifier
- 收尾异常不覆盖原始终止原因

**错误处理**：
- COMPLETE_REQUEST 后 FINAL_VALIDATION 失败 → 结构化反馈 → FEEDING_BACK → DECIDING，不能直接进入 COMPLETED
- 连续 FINAL_VALIDATION 失败超过 max_repair_attempts → LIMIT_REACHED

### 3.2 治理护栏（FC-2）

**管线**：`Action → SchemaValidator → ActionNormalizer → NormalizedAction → RuleEngine → PriorityMerger → GuardrailResult`

**输入**：Action（tool_name, parameters, raw）

**行为**：
- SchemaValidator 校验 parameters 是否符合工具注册的 parameters_schema，不合法则返回 VALIDATION_ERROR
- ActionNormalizer 将校验通过的 Action 规范化：路径转绝对路径、解析 Shell 程序与参数分离、大小写统一、符号链接解析，生成不可变 NormalizedAction
- RuleEngine 对 NormalizedAction 执行所有注册 Rule，收集全部匹配结果
- PriorityMerger 按 BLOCK > REQUEST_APPROVAL > ALLOW 合并
- 无规则匹配时默认 BLOCK
- 内置规则（WorkspaceBoundaryRule、CredentialLeakRule、UnregisteredToolRule、ModeRestrictionRule）不可关闭

**输出**：GuardrailResult（decision, rule_ids, reason_codes, human_readable_message, recoverable, normalized_action, action_fingerprint）

**边界条件**：
- 未注册工具 → BLOCK
- 未知 Action 类型 → BLOCK
- 路径归属不明确 → BLOCK
- 命令不在允许列表 → BLOCK
- 内置规则不得被配置关闭或覆盖

**错误处理**：
- Schema 校验失败 → 返回结构化 VALIDATION_ERROR，不进入执行阶段
- 无法规范化 → BLOCK
- 不可恢复的绝对禁止操作 → FAILED；可恢复违规 → FEEDING_BACK → DECIDING

### 3.3 停机条件（FC-3）

**输入**：SessionState（steps_used, llm_calls_used, token_used, cost_used, action_fingerprint_history, failure_fingerprint_history），以及当前状态和事件上下文

**行为**：StopPolicy 在以下时机均检查是否满足停机条件：
- 每次状态转换前后
- LLM 调用完成后
- 审批等待超时检查
- 工具执行完成后
- 传感器执行完成后
- FEEDING_BACK 完成后

**输出**：StopDecision（should_stop: bool, terminal_state: AgentState, reason: str）

**条件与终态**：

| 条件 | 终态 |
|------|------|
| 当前状态为 FINAL_VALIDATION，全部必需传感器 PASSED，ObjectiveVerifier 通过 | COMPLETED |
| 达到 max_steps / max_llm_calls | LIMIT_REACHED |
| 会话超时 / token_budget 或 cost_budget 耗尽 | LIMIT_REACHED |
| 连续重复 action_fingerprint ≥ no_progress_threshold | LIMIT_REACHED |
| 连续相同 failure_fingerprint ≥ no_progress_threshold | LIMIT_REACHED |
| 用户拒绝审批 / 用户主动取消 / Ctrl+C | CANCELLED |
| 不可恢复错误（凭据错误、工作区损坏、安全边界失效） | FAILED |

**边界条件**：
- COMPLETED 必须经代码验证后由 StopPolicy 判定，不来自 LLM 自我声明
- COMPLETED 仅在 FINAL_VALIDATION 状态下可达；INTERMEDIATE_VALIDATION 通过后只能进入 FEEDING_BACK，不能直接进入 COMPLETED
- action_fingerprint 与 failure_fingerprint 分别跟踪，不混用
- 所有终态均进入 FINALIZING

**错误处理**：
- 多个条件同时满足时按优先级：FAILED > CANCELLED > LIMIT_REACHED > COMPLETED
- 收尾异常不覆盖原始终止原因

### 3.4 审批流程（FC-4）

**输入**：GuardrailResult（decision=REQUEST_APPROVAL），包含 normalized_action、action_fingerprint、reason_codes

**行为**：
- ApprovalManager 创建 ApprovalRequest（绑定 session_id, request_id, normalized_action, action_fingerprint, 命中规则及风险说明, 工作区/文件状态快照, 创建时间, 过期时间）
- 主循环进入 AWAITING_APPROVAL 状态
- 用户通过 CLI（`codeguard approve/reject <request_id>`）或 WebUI 点击批准/拒绝
- 批准后重新验证路径、参数和工作区状态 → EXECUTING
- 拒绝或超时 → CANCELLED

**输出**：ApprovalResult（request_id, decision: APPROVED/REJECTED/TIMEOUT, validated_at, validator_notes）

**边界条件**：
- 批准仅用一次，Action 内容变化后立即失效
- 批准绑定具体 NormalizedAction，不能成为后续动作的通用授权
- LLM 不能自行创建或批准审批
- 不能通过提示词绕过审批
- 审批超时时间可配置，默认 300s

**错误处理**：
- Action 内容变化后批准失败 → 返回明确错误，需重新 Guardrail 检查
- 请求过期 → 返回"审批已过期"
- session 不匹配 → 拒绝

### 3.5 反馈闭环与验证（FC-5）

**两种验证类型**：

| 类型 | 触发条件 | 通过后 | 失败后 |
|------|---------|--------|--------|
| INTERMEDIATE_VALIDATION | 普通工具执行（写入/运行命令等） | FEEDING_BACK → DECIDING | FEEDING_BACK → DECIDING |
| FINAL_VALIDATION | COMPLETE_REQUEST | COMPLETED | FEEDING_BACK → DECIDING（≤ max_repair） |

**输入**：ToolResult（需验证时），或 COMPLETE_REQUEST 触发 FINAL_VALIDATION

**行为**：
- SensorPolicy 根据当前 Action 类型和任务状态决定需要运行的传感器
- SensorRunner 执行传感器（通过 SensorDefinition 提供的 program+args 数组）
- 解析器（PytestParser / RuffParser / MypyParser / GenericParser）解析原始输出
- FeedbackClassifier 输出三层分类结果
- FINAL_VALIDATION 时 ObjectiveVerifier 综合所有必需传感器结果判断是否通过
- 结构化反馈格式化为 LLM 上下文，回灌到下一轮

**输出**：FeedbackResult（sensor_id, program, args, status, failure_category, exit_code, summary, diagnostics, duration, retryable, raw_output_truncated, failure_fingerprint, validation_type）

**三层分类**：
- 第一层：PASSED / FAILED / EXECUTION_ERROR / TIMEOUT / UNAVAILABLE
- 第二层：TEST_ASSERTION_FAILURE / TEST_COLLECTION_ERROR / SYNTAX_ERROR / TYPE_CHECK_FAILURE / LINT_VIOLATION / IMPORT_OR_DEPENDENCY_ERROR / CONFIGURATION_ERROR / TOOL_NOT_FOUND / PROCESS_CRASH / TIMEOUT / UNKNOWN_FAILURE
- 第三层：诊断详情（测试名称、规则编号、错误码、文件路径、行号、消息）

**边界条件**：
- 不是所有 Action 都必须运行完整传感器；只读操作（read_file/list_directory 等）直接进入 FEEDING_BACK
- 修改文件、运行命令和 COMPLETE_REQUEST 按 SensorPolicy 触发验证
- Harness 代码判断"是否正确"，LLM 决定"下一步怎么修"
- UNKNOWN_FAILURE 不降级判为 PASSED
- 必需传感器不可用时 → FAILED；可选传感器不可用时 → 警告并继续

**错误处理**：
- pytest 无测试用例 / 解析器无法解析 / UNAVAILABLE → 不降级为 PASSED
- 同一 failure_fingerprint 连续出现 ≥ no_progress_threshold → 无进展停机
- 单传感器超时受 timeout_per_sensor 限制，可重试受 max_repair_attempts 限制
- 原始输出在存储前必须经 SecretRedactor 脱敏和大小截断

### 3.6 工具系统（FC-6）

**工具执行管线**（不可绕过 Guardrail）：
```
ToolRegistry.lookup → SchemaValidator 校验参数
→ ActionNormalizer 生成 NormalizedAction
→ Guardrail.check
→ (如需 AWAITING_APPROVAL)
→ ExecutionBoundary 执行
→ ToolResult 规范化（脱敏 + 截断）
→ Tracer/Audit 记录
→ (如需) 触发 SensorRunner
→ 结果回灌主循环
```

**输入**：Action（tool_name, parameters, raw）

**行为**：
- ToolRegistry 根据 tool_name 查找已注册的 ToolDefinition
- SchemaValidator 校验 parameters 是否符合 ToolDefinition.parameters_schema
- 校验通过后进入 Guardrail 管线
- Guardrail 通过后由 ExecutionBoundary 执行 handler
- 使用临时文件 + 原子替换进行写入操作
- 执行前再次验证工作区边界（TOCTOU 防护）

**输出**：ToolResult（tool_name, status, output_summary, diagnostics, exit_code, changed_files, duration, truncated, error_category, audit_id）

**第一版工具清单**：

| 工具 | 类别 | 默认风险 |
|------|------|---------|
| read_file | 文件 | ALLOW（限工作区内 + 大小上限 + 允许编码） |
| list_directory | 文件 | ALLOW（结果数量/深度/总大小上限） |
| find_files | 文件 | ALLOW（默认排除敏感目录） |
| search_text | 文件 | ALLOW |
| write_file | 文件 | ALLOW（新建/覆盖带指纹）/ REQUEST_APPROVAL（大范围/受保护文件） |
| apply_patch | 文件 | ALLOW（基于预期旧内容，上下文不匹配时失败） |
| delete_file | 文件 | REQUEST_APPROVAL |
| run_process | Shell | 按程序白名单，shell=False，结构化 program+args；Guardrail 根据副作用返回 ALLOW / REQUEST_APPROVAL / BLOCK |
| run_tests | 测试 | ALLOW（由可信 SensorDefinition 提供固定 program+args） |
| run_typecheck | 测试 | ALLOW（由可信 SensorDefinition 提供固定 program+args） |
| run_lint | 测试 | ALLOW（内置可信 SensorDefinition） |
| memory_search | 记忆 | ALLOW |
| memory_read | 记忆 | ALLOW |
| memory_propose_write | 记忆 | ALLOW（仅 PENDING） |
| memory_list | 记忆 | ALLOW |

**边界条件**：
- 任何工具不能绕过 Guardrail 直接调用 handler
- 未知工具 → BLOCK
- 参数无效 → VALIDATION_ERROR，不进入执行阶段
- 文件工具默认排除 .git/.venv/node_modules/构建目录/敏感文件
- 二进制文件不直接注入 LLM 上下文
- run_process 拒绝 Shell 元字符（|, >, <, &&, ||, ;, $, `` ` ``）
- 传感器命令由可信 SensorDefinition 提供，不由 LLM 自由拼接或修改
- run_tests、run_typecheck 仅当使用可信 SensorDefinition 提供的固定 program+args 时标注为 ALLOW；若 LLM 通过 run_process 直接调用测试命令，则按 run_process 的 Guardrail 规则（程序白名单 + 参数校验 + 副作用评估）处理
- 任意 run_process 仍然经过程序白名单、参数校验和 Guardrail 管线，根据副作用和风险等级返回 ALLOW / REQUEST_APPROVAL / BLOCK

**错误处理**：
- write_file 覆盖已有文件时 expected_sha256 不匹配 → 拒绝写入，报告文件已变化
- apply_patch 上下文不匹配 → 失败，不模糊应用到其他位置
- 大范围修改 / 受保护文件修改 / 整文件覆盖 → REQUEST_APPROVAL
- delete_file 始终 REQUEST_APPROVAL（即使在工作区内）
- 所有工具输出经大小限制 + SecretRedactor 后进入 trace/LLM 上下文

### 3.7 记忆系统（FC-7）

**存储**：`%LOCALAPPDATA%\CodeGuard\projects\<project_id>\memory.json`，含 schema_version

**输入**：MemoryQuery（type, tags, keywords, top_k, context_budget）或 MemoryWriteRequest（memory_propose_write 创建的 PENDING 候选）

**行为**：
- MemoryRetriever 按确定性规则检索：project_id 过滤 → type 过滤 → 精确标签匹配 → 关键词匹配 → 按 trust_level + 更新时间排序 → 取 top_k → 按 context_budget 截断
- 写入使用临时文件 + 原子替换，同一项目使用进程内锁
- 文件损坏时保留备份并报告错误，不静默清空

**输出**：list[MemoryRecord] 或 WriteResult（status, record_id）

**记录结构**：id, project_id, type, content, tags, keywords, source, trust_level, status, created_at, updated_at, session_id

**type**：PROJECT_CONVENTION / APPROVED_DECISION / TASK_SUMMARY / FAILURE_RESOLUTION

**状态机**：
```
PENDING (LLM_PROPOSED 默认状态，不自动注入上下文)
  ├── USER_APPROVED → ACTIVE（用户明确批准，自动注入优先）
  ├── HARNESS_VERIFIED → ACTIVE（结构化客观结果，自动注入优先）
  ├── REJECTED（用户拒绝）
  ├── ARCHIVED（归档）
  └── DELETED（删除）
```

**信任等级**：USER_APPROVED, HARNESS_VERIFIED（自动注入优先）, LLM_PROPOSED（默认不自动注入）

**写入边界**：
- LLM 仅能通过 memory_propose_write 创建 PENDING 候选
- 会话结束时只保存：类型化/脱敏的任务摘要、验证结果、失败解决方案
- 禁止保存：完整聊天、完整测试输出、原始工具输出、原始测试失败记录、API Key、凭据、未经筛选文件内容
- 原始测试失败和完整测试输出属于当前 Session 的 Feedback/Trace，不得自动写入跨会话记忆
- 只有经过验证且值得跨会话保留的失败解决经验，才能以 FAILURE_RESOLUTION 类型写入

**边界条件**：
- Memory 类型使用代码枚举验证（MemoryType 枚举），未知类型写入时拒绝，不能静默映射
- tags 只能辅助检索，不能替代 MemoryType；类型筛选以 type 字段为准
- 记忆以结构化"参考数据"区块注入，不覆盖 system policy / Guardrail / 工具权限
- 注入前经 SecretRedactor 和长度限制
- PENDING / REJECTED / ARCHIVED / DELETED 不自动注入（DELETED 显式排除）
- trust_level 只影响排序，不授予工具权限
- 检索排序稳定，最终使用 id 作为稳定排序项
- context_budget 按字符数或统一估算单位计算

**错误处理**：
- JSON 损坏 → 保留备份，报告错误
- 单条 content 超上限 → 拒绝写入
- max_records 超限 → 拒绝新写入

### 3.8 配置系统（FC-8）

**输入**：TOML 文件（用户级和项目级）+ CLI flags

**行为**：
- ConfigLoader 使用 tomllib 解析 TOML 文件
- SchemaValidator 严格校验类型和数值范围
- ConfigMerger 按字段类型安全合并（见下方逐字段合并规则表）
- 加载成功后生成不可变 EffectiveConfig，记录配置来源（不含凭据）
- 提供 `codeguard config show` 展示脱敏后有效配置及每项来源

**输出**：EffectiveConfig（不可变运行时对象）

**优先级**：内置默认值 → 用户级 `%LOCALAPPDATA%\CodeGuard\config.toml` → 项目级 `codeguard.toml` → CLI flags

**安全合并**：按字段类型定义确定性合并规则。以下规则在 ConfigMerger 中编码实现，不依赖配置书写顺序：

| 字段 | 所属类别 | 合并规则 | 安全边界 |
|------|---------|---------|---------|
| `project_root` | workspace | 上层指定，下层不可覆盖 | 项目配置不能更改工作区根目录 |
| `additional_protected_paths` | workspace | 取并集 | 保护路径只能增加不能减少 |
| `excluded_paths` | workspace | 取并集 | 排除路径只能增加不能减少 |
| `provider`, `model` | llm | CLI flags 覆盖配置文件 | 项目配置不能更改 |
| `max_output_tokens` | llm | 取更小值 | 输出限制只能收紧 |
| `request_timeout` | llm | 取更小值 | 超时只能更短 |
| `credential_profile` | llm | 上层覆盖下层 | 仅用户级配置可设置 |
| `max_steps`, `max_llm_calls`, `max_repair_attempts` | loop | 取更小值 | 限制只能收紧不能放宽 |
| `session_timeout` | loop | 取更小值 | 超时只能更短不能更长 |
| `tool_timeout` | loop | 取更小值 | 全局工具超时只能更短 |
| `no_progress_threshold` | loop | 取更小值 | 无进展判定阈值只能更严格 |
| `token_budget`, `cost_budget` | loop | 取更小值 | 预算只能更低不能更高 |
| `enabled_tools` | tools | 取交集 | 只能缩小可用工具集 |
| `disabled_tools` | tools | 取并集 | 禁用工具只能增加不能减少 |
| `per_tool_timeouts` | tools | 逐工具取更小值，且不得超过 `LoopConfig.tool_timeout` | 按工具分别收紧，不能超过全局上限 |
| `required_sensors` | sensors | 取并集 | 项目配置不能删除上层必需的传感器 |
| `sensor_order` | sensors | 下层追加到上层末尾，去重 | 不能删除上层必需的传感器 |
| `timeout_per_sensor` | sensors | 取更小值 | 传感器超时只能更短 |
| `output_limit` | sensors | 取更小值 | 输出限制只能更严 |
| `enabled` | memory | 上层覆盖下层 | 项目配置不能启用已被上层禁用的记忆 |
| `max_records`, `top_k`, `context_budget` | memory | 取更小值 | 资源限制只能收紧 |
| `allowed_types` | memory | 取交集 | 允许的记忆类型只能减少 |
| `web_port`, `bind_address` | ui | CLI flags 覆盖配置文件 | 默认 127.0.0.1 不可通过项目配置改为 0.0.0.0 |
| `approval_timeout` | ui | 用户级配置和 CLI 可在 5–60 秒内设置任意值；项目级配置只能缩短用户级限制（取更小值），不能放宽 | Mock 超时场景固定为 5 秒，不受配置影响 |
| `cli_timeout` | approval | 仅允许用户级配置或 CLI 在 10–600 秒内设置；项目配置不得设置此字段 | 本地 CLI 审批超时，默认 300 秒 |
| `mode` | mode | 代码层不可配置升级 | local/test/demo 不可通过配置文件切换 |

> `tool_timeout` 在 `LoopConfig` 中作为全局默认超时。`ToolsConfig` 改为可选的 `per_tool_timeouts: dict[str, int]` 映射，仅对指定工具覆盖全局默认值，且逐工具取值不得超过 `LoopConfig.tool_timeout`。运行时优先使用 `per_tool_timeouts`，未指定的工具回退到 `LoopConfig.tool_timeout`。

**CLI 审批超时配置**：新增 `ApprovalConfig`，以 `approval` 配置类别纳入 `EffectiveConfig`：

```python
@dataclass
class ApprovalConfig:
    cli_timeout: int  # 本地 CLI 审批超时，默认 300 秒，仅用户级或 CLI 可设置，范围 10-600
```

`approval_timeout` 在 `UIConfig` 中仅控制 WebUI Mock 审批（默认 15s，用户级/CLI 可设 5-60s，项目级只能缩短）。Mock 超时场景固定为 5 秒，不受任何配置影响。CLI 审批超时由 `ApprovalConfig.cli_timeout` 控制（默认 300s，仅用户级或 CLI 可设）。两者互不覆盖，分别对应各自模式的超时默认值。

**第一版配置类别**：

| 类别 | 内容 | 安全约束 |
|------|------|---------|
| workspace | project_root, additional_protected_paths, excluded_paths | 不能扩大范围 |
| llm | provider, model, max_output_tokens, request_timeout, credential_profile | 不保存真实 Key |
| loop | max_steps, max_llm_calls, max_repair_attempts, session_timeout, tool_timeout, no_progress_threshold, token_budget, cost_budget | 有代码安全范围 |
| tools | enabled_tools, disabled_tools, per_tool_timeouts | 只能缩小不可扩大 |
| sensors | required_sensors, sensor_order, timeout_per_sensor, output_limit | 命令使用 program+args 数组 |
| memory | enabled, max_records, top_k, context_budget, allowed_types | 凭据不入记忆 |
| ui | web_port, bind_address, approval_timeout | 本地默认 127.0.0.1 |
| approval | cli_timeout | 本地 CLI 审批超时，默认 300s |
| mode | local / test / demo | 代码层不可配置升级 |

**边界条件**：
- 未知字段 → 启动失败并报告精确位置
- 类型错误 / 越界值 / 冲突 → 启动失败，不静默回退
- 不支持 include / 命令替换 / 环境变量插值
- 任何层不能关闭内置不可关闭规则
- 项目配置不能扩大工具权限或路径范围
- 项目配置不能切换 WebUI 的 DemoCompositionRoot 为 LOCAL

**错误处理**：
- 配置错误 → fail closed，给出明确错误提示
- 项目配置中涉及危险命令扩展 → 至少需用户级可信配置或人工确认

### 3.9 WebUI 演示模式（FC-9）

**技术栈**：FastAPI + Jinja2 服务端模板 + HTML/CSS + 少量原生 JavaScript。REST + 简单轮询，不引入 WebSocket。不引入 React、Node.js 或前端构建流程（npm/webpack/vite）。

**关于 Open Design**：本项目 WebUI 是纯后端 Harness 的附属演示界面，包含 3–4 个简单页面（场景选择、状态机可视化、审批操作）。根据课程 §3.6 的推荐，使用 Open Design 完成设计工作流：

- **Open Design 版本**：v0.16.1
- **Skill 准确名称**：`Web Prototype`（以文档化模式运行，不产出 HTML/CSS/JS 实现代码）
- **设计系统**：Vercel Design System（`design-systems/vercel`）
- **设计产物目录**：`docs/design/open-design/`（含 DESIGN.md、INFORMATION_ARCHITECTURE.md、WIREFRAME_SPEC.md、5 个 ASCII 线框图、ROUND_01_REVIEW.md、ROUND_01_HUMAN_DECISIONS.md）
- **Open Design 不是运行依赖**：设计工作流完成后，实现仍采用 FastAPI + Jinja2 + HTML/CSS + 原生 JavaScript，不引入 Open Design 运行时。设计规范以仓库内 `docs/design/open-design/DESIGN.md` 为实现依据（该文件包含颜色、间距、排版、组件等完整视觉令牌），不以代码依赖方式引入。不从 Open Design 安装目录复制 tokens.css 或其他文件。
- 详见 `docs/design/open-design/`。

**定位**：安全、可重复的机制演示界面，非在线编码工具

**输入**：用户选择的预设场景 ID、审批操作（批准/拒绝）、步骤控制（启动/下一步/自动运行/重置）

**行为**：
- DemoCompositionRoot 装配真实 Harness 核心（状态机、Guardrail 引擎、ApprovalManager、FeedbackClassifier、StopPolicy、Tracer）
- Mock 外部副作用边界：ScriptedMockLLM、场景化模拟文件系统、MockMemoryStore、MockCredentialStore
- 每个浏览器会话使用独立随机 session_id 和独立内存状态
- 状态只保存在内存中，重启后可丢失
- **审批超时**：本地 CLI 审批默认 300 秒（见 §3.4）；WebUI Mock 普通审批默认 15 秒；WebUI Mock 可配置范围 5–60 秒；专门的 Mock 超时场景预设 5 秒。超时后产生 TIMEOUT → Session 进入 CANCELLED，待审批动作绝不执行。第一版不提供暂停倒计时功能。
- **FakeClock**：审批超时测试使用 `FakeClock`/可注入时钟，不真实等待。

**输出**：实时状态机可视化、治理详情（脱敏）、反馈详情、Trace 时间线

**演示场景**：
1. 危险动作 BLOCK → Guardrail 拦截 → LLM 收到反馈后改变 Action
2. REQUEST_APPROVAL 审批 → AWAITING_APPROVAL → 批准/拒绝/超时
3. 反馈闭环 → 第一次失败 → FeedbackClassifier 分类 → 回灌 → LLM 改变 Action → 最终通过

**安全边界**：
- DemoCompositionRoot 不导入真实 DeepSeekAdapter、KeyringCredentialStore、LocalToolExecutor 或网络客户端
- 即使环境中存在 API Key 或真实配置文件，demo mode 也不读取或使用
- 不提供任意任务输入、Shell 命令输入、真实文件上传、任意工具调用按钮
- 本地 WebUI 默认绑定 127.0.0.1
- Render 部署绑定 0.0.0.0 + 平台端口，提供 `/health` 健康检查

**边界条件**：
- 审批仅作用于当前 Mock session 中的 pending request
- 批准绑定 session_id + approval_request_id + normalized_action fingerprint
- 批准仅允许 MockToolDispatcher 返回预设结果，不调用真实 handler
- 不同用户不能查看其他会话或修改共享状态
- **窄屏自适应**：桌面优先，目标宽度 1366×768 及以上。窄屏 <768px 时只保证基本可读、可滚动和可操作：多栏仪表盘按顺序堆叠为单栏；Agent 状态步进器保持横向滚动；表格和较宽 Trace 内容允许组件内部横向滚动；审批模态宽度限制在视口内，按钮可纵向排列；不得出现页面级不可控横向溢出；Mock 横幅保持可见；关键按钮触达区域 ≥44×44px。不创建独立移动端页面、移动导航或专门移动端交互流程。自动化验收至少检查 375px 宽视口：页面可打开、关键文字可读、场景可选择、审批可操作、显式滚动区域可用、无遮挡关键按钮的布局错误。

**错误处理**：
- 请求过期 / session 不匹配 / Action 变化 → 批准失败，返回明确错误
- 服务重启后所有演示状态丢失（无需持久化）

---

## 4. 非功能性需求

### 4.1 性能
- LLM 决策时间由外部 API 决定，Harness 本身开销 < 100ms/轮
- 传感器执行受超时控制（默认 30s/传感器）
- 本地 WebUI 冷启动 < 2s

### 4.2 安全（含凭据威胁模型）

**威胁模型**：

| 威胁 | 缓解措施 |
|------|---------|
| API Key 泄露到 Git | 仅通过 Windows Credential Manager 存储，不入配置文件/日志/代码 |
| 路径穿越逃逸 | ActionNormalizer 规范化 + WorkspaceBoundaryRule + 执行前再次验证 |
| Shell 注入 | run_process 使用 program+args 结构化形式，shell=False，拒绝元字符 |
| 提示词注入篡改 Guardrail | 内置规则代码实现不可关闭，记忆不覆盖系统策略 |
| 敏感信息进入 LLM 上下文 | SecretRedactor 覆盖所有数据路径 |
| 审批绕过 | 批准绑定具体 Action Fingerprint，变化后失效 |
| 演示环境升级为真实执行 | DemoCompositionRoot 不导入 DeepSeekAdapter、KeyringCredentialStore、LocalToolExecutor、网络客户端和宿主文件系统执行器 |

**凭据管理**：
- 存储：Windows Credential Manager + keyring 库
- 录入：隐藏输入，不通过命令行参数接收
- 读取：仅 LLM API 请求前按需读取，不入 LLM 上下文
- 清除：`codeguard key clear --provider deepseek`
- 不可用时：fail closed，报错退出
- 内存：Python 不保证字符串内存擦除，文档诚实说明

### 4.3 可用性
- CLI 提供清晰的错误信息和配置引导
- 首次运行引导用户安全录入 API Key
- WebUI 展示状态机实时状态，操作按钮明确

### 4.4 可观测性
- Tracer 记录完整状态转换序列
- 审计日志记录所有 Guardrail 决策
- 脱敏后输出到 CLI 和 trace 文件

---

## 5. 系统架构

### 5.1 组件图

```
┌─────────────────────────────────────────────────────────┐
│                     CodeGuard Harness                      │
│                                                           │
│  ┌──────────┐  ┌──────────────────────────────────────┐  │
│  │ CLI/WebUI  │  │         Composition Root              │  │
│  │ (入口层)   │  │  Local / Test / Demo                   │  │
│  └─────┬────┘  └──────────────┬───────────────────────┘  │
│        │                      │                          │
│  ┌─────▼──────────────────────▼───────────────────────┐  │
│  │            Agent 主循环 (显式状态机)                 │  │
│  │  状态转换: INITIALIZING → ... → FINALIZING           │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────────┐  │
│  │ ToolRegi- │ │ Guardrail│ │   SensorRunner + Parsers  │  │
│  │ stry +    │ │ 引擎     │ │   FeedbackClassifier      │  │
│  │ Dispatcher│ │          │ │                          │  │
│  └──────────┘ └──────────┘ └──────────────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────────┐  │
│  │ Memory   │ │Credential│ │   Config + Tracer +       │  │
│  │ Store +  │ │ Store    │ │   StopPolicy              │  │
│  │ Retriever│ │          │ │                          │  │
│  └──────────┘ └──────────┘ └──────────────────────────┘  │
│                                                           │
│  ┌──────────────────────────────────────────────────────┐│
│  │  LLMClient 接口                                       ││
│  │  ├── ScriptedMockLLM (强制, 离线测试/CI/Demo)        ││
│  │  └── DeepSeekAdapter (真实 API, OpenAI-compatible)   ││
│  └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### 5.2 数据流

```
用户输入 → CLI/WebUI → Harness.start()
  → ConfigLoader 加载配置
  → CompositionRoot 装配组件
  → 主循环开始
    → BUILDING_CONTEXT: MemoryRetriever + ContextBuilder 组织上下文
    → DECIDING: LLMClient.generate() → ActionParser 解析
    → GOVERNING: ActionNormalizer → RuleEngine → PriorityMerger
    → AWAITING_APPROVAL: ApprovalManager 等待用户
    → EXECUTING: ToolDispatcher.dispatch() → ExecutionBoundary
    → VALIDATING: SensorRunner.run() → FeedbackClassifier
    → FEEDING_BACK: 格式化反馈 → 存入上下文
    → StopPolicy 判断停机
  → FINALIZING: 固化记忆 → 关闭 trace → 清理资源
  → 返回 SessionResult
```

### 5.3 外部依赖

| 依赖 | 用途 | 使用条件 |
|------|------|---------|
| DeepSeek API（OpenAI-compatible） | 真实 LLM 调用 | LOCAL 模式，仅 LLM 请求 |
| keyring | Windows Credential Manager 对接 | LOCAL 模式 |
| Python 标准库（argparse, tomllib, subprocess, json, pathlib） | CLI、配置、进程执行 | 全部模式 |
| FastAPI + Jinja2 + uvicorn | WebUI | DEMO 模式 |
| pytest | 单元测试 | 开发/CI |
| PyInstaller | Windows exe 打包 | 分发构建 |

---

## 6. 数据模型

### 6.1 Action

```python
from enum import Enum

class ActionKind(Enum):
    TOOL_CALL = "tool_call"
    COMPLETE_REQUEST = "complete"

@dataclass
class Action:
    kind: ActionKind
    tool_name: Optional[str]          # TOOL_CALL 时必填
    parameters: Optional[dict]        # TOOL_CALL 时必填
    summary: Optional[str]            # COMPLETE_REQUEST 时携带完成摘要/依据
    raw: str                          # LLM 原始输出（脱敏、截断后的审计值）

@dataclass
class NormalizedAction:
    kind: ActionKind
    tool_name: Optional[str]
    normalized_parameters: Optional[dict]
    action_fingerprint: str
    original_raw: str                 # 审计保留（脱敏、截断）
    normalized_at: datetime
```

### 6.2 AgentState

```python
from enum import Enum

class AgentState(Enum):
    # 运行态（9 个）
    INITIALIZING = "initializing"
    BUILDING_CONTEXT = "building_context"
    DECIDING = "deciding"
    GOVERNING = "governing"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    INTERMEDIATE_VALIDATION = "intermediate_validation"
    FINAL_VALIDATION = "final_validation"
    FEEDING_BACK = "feeding_back"

    # 终态（4 个）
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LIMIT_REACHED = "limit_reached"
```

> FINALIZING 是终态之后的生命周期收尾阶段（固化记忆、关闭 trace、清理资源），不计入 13 个 AgentState。所有终态（COMPLETED / FAILED / CANCELLED / LIMIT_REACHED）均进入 FINALIZING。

### 6.3 LLMResponse

```python
@dataclass
class LLMResponse:
    content: str                       # 文本回复
    next_action: Action                # 每轮只返回一个 Action
    finish_reason: str                 # stop / tool_calls / length / error
    model: str
    token_used: int
    cost_used: Decimal
    raw_response: str                  # 审计保留（脱敏、截断后）
```

### 6.4 ToolDefinition

```python
@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters_schema: dict  # JSON Schema
    handler: Callable
    category: ToolCategory  # FILE / SHELL / TEST / MEMORY
    side_effect: bool
    default_risk: RiskLevel  # 仅元数据，Guardrail 作最终决定
    supported_modes: list[RunMode]  # LOCAL / TEST / DEMO
    result_schema: Optional[dict]
    timeout_limit: int  # 秒
```

### 6.5 ToolResult

```python
@dataclass
class ToolResult:
    tool_name: str
    status: ToolStatus  # SUCCESS / FAILURE / VALIDATION_ERROR / TIMEOUT
    output_summary: str  # 脱敏 + 截断
    diagnostics: list[Diagnostic]
    exit_code: Optional[int]  # None 当不适用时
    changed_files: list[str]
    duration: float
    truncated: bool
    error_category: Optional[str]
    audit_id: str
```

### 6.6 GuardrailResult

```python
@dataclass
class GuardrailResult:
    decision: GuardrailDecision  # BLOCK / REQUEST_APPROVAL / ALLOW
    rule_ids: list[str]
    reason_codes: list[str]
    human_readable_message: str
    recoverable: bool
    normalized_action: NormalizedAction
    action_fingerprint: str
```

### 6.7 ApprovalRequest

```python
@dataclass
class ApprovalRequest:
    request_id: str
    session_id: str
    normalized_action: NormalizedAction
    action_fingerprint: str
    matched_rules: list[str]
    risk_summary: str
    workspace_snapshot: dict  # 相关工作区状态
    created_at: datetime
    expires_at: datetime
    status: ApprovalStatus  # PENDING / APPROVED / REJECTED / TIMEOUT
```

### 6.8 FeedbackResult

```python
@dataclass
class FeedbackResult:
    sensor_id: str
    program: str
    args: list[str]
    status: SensorStatus  # PASSED / FAILED / EXECUTION_ERROR / TIMEOUT / UNAVAILABLE
    failure_category: Optional[FailureCategory]  # None 当 PASSED 时
    exit_code: Optional[int]  # None 当不适用或 PASSED 时
    failure_fingerprint: Optional[str]  # None 当 PASSED 时
    validation_type: ValidationType  # INTERMEDIATE / FINAL
    summary: str
    diagnostics: list[Diagnostic]
    duration: float
    retryable: bool
    raw_output_truncated: str  # 脱敏 + 截断
```

### 6.9 SensorDefinition

```python
@dataclass
class SensorDefinition:
    name: str
    program: str
    args: list[str]
    cwd: Optional[str]
    timeout: int
    parser: str  # 解析器标识：pytest / ruff / mypy / generic
    required: bool  # True=必需, False=可选
    allowed_exit_codes: set[int]
    output_limit: int
```

### 6.10 Diagnostic

```python
@dataclass
class Diagnostic:
    file: Optional[str]
    line: Optional[int]
    column: Optional[int]
    code: Optional[str]  # 规则编号或错误码
    message: str
    category: str  # 与 FailureCategory 对应
```

### 6.11 MemoryRecord

```python
@dataclass
class MemoryRecord:
    id: str
    project_id: str
    type: MemoryType  # PROJECT_CONVENTION / APPROVED_DECISION / TASK_SUMMARY / FAILURE_RESOLUTION
    content: str
    tags: list[str]
    keywords: list[str]
    source: str
    trust_level: TrustLevel  # USER_APPROVED / HARNESS_VERIFIED / LLM_PROPOSED
    status: MemoryStatus  # PENDING / ACTIVE / REJECTED / ARCHIVED / DELETED
    created_at: datetime
    updated_at: datetime
    session_id: str
```

### 6.12 SessionState

```python
@dataclass
class SessionState:
    session_id: str
    current_state: AgentState
    pending_action: Optional[NormalizedAction]
    guardrail_decision: Optional[GuardrailResult]
    approval_request_id: Optional[str]
    steps_used: int
    llm_calls_used: int
    token_used: int
    cost_used: Decimal
    action_fingerprint_history: list[str]
    failure_fingerprint_history: list[str]
    started_at: datetime
```

### 6.13 SessionResult

```python
@dataclass
class SessionResult:
    session_id: str
    terminal_state: AgentState
    steps_total: int
    llm_calls_total: int
    token_total: int
    cost_total: Decimal
    duration: float
    guardrail_decisions: list[GuardrailResult]
    feedback_results: list[FeedbackResult]
    trace: list[TraceEvent]
    error: Optional[str]  # 最终错误信息（脱敏）
```

### 6.14 配置模型

```python
@dataclass
class EffectiveConfig:
    workspace: WorkspaceConfig
    llm: LLMConfig
    loop: LoopConfig
    tools: ToolsConfig
    sensors: SensorsConfig
    memory: MemoryConfig
    ui: UIConfig
    approval: ApprovalConfig
    mode: RunMode
    source: dict[str, str]  # 每项配置的来源标识

@dataclass
class WorkspaceConfig:
    project_root: Path
    additional_protected_paths: list[Path]
    excluded_paths: list[Path]

@dataclass
class LLMConfig:
    provider: str  # "deepseek"
    model: str  # "deepseek-v4-flash"
    max_output_tokens: int
    request_timeout: int
    credential_profile: str  # "default"

@dataclass
class LoopConfig:
    max_steps: int
    max_llm_calls: int
    max_repair_attempts: int
    session_timeout: int
    tool_timeout: int
    no_progress_threshold: int
    token_budget: int
    cost_budget: Decimal

@dataclass
class ToolsConfig:
    enabled_tools: list[str]
    disabled_tools: list[str]
    per_tool_timeouts: dict[str, int]  # 可选，按工具覆盖全局 tool_timeout

@dataclass
class SensorsConfig:
    required_sensors: list[str]
    sensor_order: list[str]
    timeout_per_sensor: int
    output_limit: int

@dataclass
class MemoryConfig:
    enabled: bool
    max_records: int
    top_k: int
    context_budget: int
    allowed_types: list[str]  # MemoryType 枚举值列表

@dataclass
class UIConfig:
    web_port: int              # 默认 8080
    bind_address: str          # 默认 "127.0.0.1"
    approval_timeout: int      # WebUI Mock 审批超时秒数，默认 15，范围 5-60

@dataclass
class ApprovalConfig:
    cli_timeout: int           # 本地 CLI 审批超时秒数，默认 300，范围 10-600
```

---

## 7. 状态机与转换

### 7.1 状态转换矩阵

| 当前状态 | 事件 | 下一状态 |
|---------|------|---------|
| INITIALIZING | 启动装配完成 | BUILDING_CONTEXT |
| INITIALIZING | 安全 backend 检查失败 | FAILED |
| BUILDING_CONTEXT | 上下文组织完成 | DECIDING |
| DECIDING | LLM 返回有效 Action | GOVERNING |
| DECIDING | LLM 解析失败 | FEEDING_BACK |
| DECIDING | LLM 返回 COMPLETE_REQUEST | FINAL_VALIDATION |
| GOVERNING | ALLOW | EXECUTING |
| GOVERNING | REQUEST_APPROVAL | AWAITING_APPROVAL |
| GOVERNING | BLOCK（可恢复） | FEEDING_BACK |
| GOVERNING | BLOCK（不可恢复） | FAILED |
| AWAITING_APPROVAL | 用户批准 → 重新校验 | EXECUTING |
| AWAITING_APPROVAL | 用户拒绝 | CANCELLED |
| AWAITING_APPROVAL | 超时 | CANCELLED |
| EXECUTING | 执行成功（需验证） | INTERMEDIATE_VALIDATION |
| EXECUTING | 执行成功（只读操作） | FEEDING_BACK |
| EXECUTING | 可恢复错误 | FEEDING_BACK |
| EXECUTING | 不可恢复错误 | FAILED |
| INTERMEDIATE_VALIDATION | 全部 PASSED | FEEDING_BACK |
| INTERMEDIATE_VALIDATION | 失败（≤ max_repair） | FEEDING_BACK |
| INTERMEDIATE_VALIDATION | 失败（超限） | LIMIT_REACHED |
| FINAL_VALIDATION | 全部 PASSED | COMPLETED |
| FINAL_VALIDATION | 失败（≤ max_repair） | FEEDING_BACK |
| FINAL_VALIDATION | 失败（超限） | LIMIT_REACHED |
| FEEDING_BACK | 回灌完成（≤ max_steps） | DECIDING |
| FEEDING_BACK | 回灌完成（超限） | LIMIT_REACHED |
| FEEDING_BACK | 连续重复 action_fingerprint | LIMIT_REACHED |
| * | 用户主动取消 / Ctrl+C | CANCELLED |
| COMPLETED / FAILED / CANCELLED / LIMIT_REACHED | 进入收尾 | FINALIZING |
| FINALIZING | 收尾完成 | （终止） |

### 7.2 验收测试（状态转换）

| 测试场景 | 覆盖的转换 |
|---------|-----------|
| 正常完成流程 | INITIALIZING → ... → COMPLETED → FINALIZING |
| LLM 声称完成但 FINAL_VALIDATION 失败后重新决策 | DECIDING(COMPLETE) → FINAL_VALIDATION → FEEDING_BACK → DECIDING |
| BLOCK 后重新决策 | GOVERNING(BLOCK) → FEEDING_BACK → DECIDING |
| 审批批准后执行 | GOVERNING(APPROVAL) → AWAITING_APPROVAL → APPROVED → EXECUTING |
| 审批拒绝 | AWAITING_APPROVAL → REJECTED → CANCELLED → FINALIZING |
| 审批超时 | AWAITING_APPROVAL → TIMEOUT → CANCELLED → FINALIZING |
| 工具执行后 INTERMEDIATE_VALIDATION 失败 | EXECUTING → INTERMEDIATE_VALIDATION → FEEDING_BACK → DECIDING |
| 工具不可恢复错误 | EXECUTING → FAILED → FINALIZING |
| 重复 action_fingerprint | FEEDING_BACK → LIMIT_REACHED → FINALIZING |
| max_steps 耗尽 | 循环 → LIMIT_REACHED → FINALIZING |
| 用户主动取消 | 任意状态 → CANCELLED → FINALIZING |

---

## 8. 凭据与分发设计

### 8.1 凭据存储

- **方案**：Windows Credential Manager + keyring 库
- **录入**：`codeguard key set --provider deepseek`，隐藏输入
- **读取**：仅 LLM API 请求前按需读取，不入 LLM 上下文
- **Profile**：`deepseek:default`（service_name: `codeguard`）
- **不可用时**：fail closed，报错退出，不自动回退
- **CLI**：`codeguard key set/status/update/clear --provider deepseek`

### 8.2 分发形态

**Windows exe（PyInstaller）**：
- 目标平台：Windows 10/11 64 位
- CPU 架构：x86-64
- 打包格式：PyInstaller 单文件 exe
- 入口：`codeguard.exe chat` / `codeguard.exe demo` / `codeguard.exe web` / `codeguard.exe key`
- 本地 WebUI 默认绑定 127.0.0.1
- 静态资源随 exe 打包
- 代码签名：第一版不进行代码签名。未签名 exe 可能触发 Windows SmartScreen，在 README 中提供 SHA-256 校验哈希和安全运行说明
- 验收测试：必须在全新 Windows 环境（如 VM 或裸机）执行安装、启动、Key 录入、CLI 和 WebUI 的完整验收

**Render 源码部署**：
- 从 Python 源码/Docker 启动 FastAPI
- 固定 DemoCompositionRoot
- 绑定 0.0.0.0 + 平台端口，提供 `/health`
- 不配置真实 API Key，不连接 Credential Manager

### 8.3 Key 安全配置方式

1. 首次运行 `codeguard key set --provider deepseek`
2. 程序检查 keyring backend 可用性
3. 隐藏输入提示录入 Key
4. Key 经 Windows Credential Manager 加密存储
5. 后续运行自动读取，不入日志/配置文件/Git

---

## 9. 技术选型与理由

| 项目 | 选择 | 理由 |
|------|------|------|
| 语言 | Python 3.12 | LLM 生态丰富，mock 测试成熟，FastAPI 原生支持 |
| CLI 框架 | argparse（Python 内置） | 零额外依赖 |
| WebUI | FastAPI + Jinja2 + HTML/CSS + JS（设计规范基于 Open Design Vercel Design System，不引入运行时依赖） | 前后端一体，无需 Node.js；通过 Open Design 的 Vercel DESIGN.md 规范指导排版、颜色、间距、组件设计 |
| 真实 LLM | DeepSeek（OpenAI-compatible API） | 用户实际需求，通过统一 LLMClient 接口接入 |
| Mock LLM | ScriptedMockLLM（自实现） | 确定性测试核心 |
| 凭据 | Windows Credential Manager + keyring | §3.1 安全要求 |
| 分发 | Windows exe（PyInstaller）+ Render 源码部署 | 两种使用场景 |
| 测试 | pytest + mock（全部离线） | 确定性测试 |
| CI | GitLab CI（unit-test job 全部使用 Mock） | 课程要求 |
| 配置 | TOML（tomllib） | Python 3.11+ 内置 |

### 9.1 CI/CD 设计

**GitLab CI（`.gitlab-ci.yml`，课程要求）**：
```yaml
unit-test:
  stage: test
  script:
    - pip install -r requirements.txt
    - pytest
  # 不硬编码 tags；由 CI Runner 自动选择
```

**GitHub Actions（`.github/workflows/ci.yml`，镜像仓库同步）**：
```yaml
name: CI
on: [push, pull_request]
jobs:
  unit-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: pytest
  build-exe:
    runs-on: windows-latest
    needs: unit-test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: pip install pyinstaller
      - run: pytest
      - run: pyinstaller --onefile --name codeguard codeguard/__main__.py
      - name: Smoke test
        run: ./dist/codeguard.exe --help
      - name: Generate SHA-256
        run: certutil -hashfile ./dist/codeguard.exe SHA256 | findstr /v "hash" > ./dist/codeguard.exe.sha256
      - uses: actions/upload-artifact@v4
        with:
          name: codeguard-exe
          path: |
            ./dist/codeguard.exe
            ./dist/codeguard.exe.sha256
```

**CI 约束**：
- 测试运行不访问真实 LLM、外部业务 API 或真实凭据
- 依赖安装阶段允许下载 PyPI 依赖
- 集成测试运行真实 Harness 核心（状态机、Guardrail、ApprovalManager、FeedbackClassifier、StopPolicy、Tracer），只 Mock/Fake LLM 与外部副作用边界
- 不配置任何真实的 LLM API Key 或 Secrets
- 不访问 Windows Credential Manager（CI 环境中不可用）
- 不输出、上传或缓存凭据相关文件
- 提供手动触发的 DeepSeek API 连通性测试脚本，但不在 CI 中自动运行

---

## 10. 领域与机制设计（Coding Agent Harness 专项）

### 10.1 领域分析

**领域**：软件开发辅助（Coding Agent）

**反馈信号** | 实现方式
运行测试/pytest | SensorRunner → PytestParser → FeedbackClassifier
代码风格检查/ruff | SensorRunner → RuffParser → FeedbackClassifier
类型检查/mypy | SensorRunner → MypyParser → FeedbackClassifier
**全部为确定性代码解析，不依赖 LLM 判断**

**危险动作** | 实现方式
文件系统逃逸 | WorkspaceBoundaryRule（路径规范化 + 多重验证）
危险 Shell 命令 | CommandWhitelistRule + run_process 结构化参数
凭据泄露 | CredentialLeakRule + 统一 SecretRedactor
未注册工具 | UnregisteredToolRule
**全部为代码实现的 Rule 接口，不依赖提示词约束**

**所需工具**：文件系统工具、结构化进程执行、测试传感器、记忆工具

**记忆需求**：跨会话项目约定、决策记录、失败解决方案；按标签+关键词检索

### 10.2 重点维度深入

**主要贡献**：治理驱动的测试反馈闭环。

Guardrail 负责约束动作空间、拦截危险操作、执行三级决策（BLOCK/REQUEST_APPROVAL/ALLOW）；Sensor/Feedback 子系统负责在动作执行后提供确定性客观信号，经三层分类后回灌 LLM，驱动自我修正。Guardrail 在前端约束"什么不能做"，Feedback 在后端验证"做得对不对"，二者组成可审计、可确定性测试的完整闭环。两部分实现内容保留如下：

**治理护栏**：
- Rule 接口 + 注册表 + 优先级合并器 + ActionNormalizer
- 内置不可关闭规则（WorkspaceBoundaryRule, CredentialLeakRule, UnregisteredToolRule, ModeRestrictionRule）
- 三级决策：BLOCK / REQUEST_APPROVAL / ALLOW
- 默认拒绝策略（无规则匹配时 BLOCK）
- 审批绑定具体 Action，不可复用

**测试反馈闭环**：
- SensorRunner 管理传感器生命周期
- 三层分类结构（执行状态 → 失败类别 → 诊断详情）
- 每种工具独立解析器（PytestParser / RuffParser / MypyParser / GenericParser）
- failure_fingerprint 识别重复失败
- 仅在所有必需传感器 PASSED 时停机

---

## 11. 验收标准

| 功能 | 验收标准 |
|------|---------|
| Agent 主循环 | 状态机完整执行 §7.1 定义的全部状态转换，可注入 ScriptedMockLLM 完成确定性测试 |
| 治理护栏 | 10 种以上预设危险场景被正确 BLOCK/REQUEST_APPROVAL/ALLOW |
| 反馈闭环 | 注入失败后 LLM 改变 Action，最终通过验证 |
| 凭据管理 | Key 经 Windows Credential Manager 存储，不出现于日志/配置/Git；支持 `codeguard key set/status/update/clear --provider deepseek` 完整生命周期 |
| 记忆系统 | 跨会话写入/读取，LLM_PROPOSED 不自动注入 |
| 配置系统 | 4 层加载 + 按字段类型安全合并，错误时 fail closed |
| WebUI 演示 | 3 个预设场景确定性执行，不调用真实 LLM、Shell、文件系统、网络或 Credential Manager；Mock 审批超时默认 15 秒、可配置 5–60 秒、超时场景 5 秒；使用 FakeClock/可注入时钟测试，不真实等待 |
| 浏览器会话隔离 | 不同浏览器 session 使用独立 session_id 和独立内存状态，不能互相干扰 |
| Demo 安全隔离 | DemoCompositionRoot 不导入 DeepSeekAdapter、KeyringCredentialStore、LocalToolExecutor 或网络客户端；即使环境中存在 API Key 或真实配置也不读取 |
| 分发 | `codeguard.exe` 可运行 CLI/Demo/Web/Key 子命令；在全新 Windows 环境可运行并安全录入 Key |
| CI | GitLab CI unit-test job + GitHub Actions 均通过，不依赖网络或真实 API Key |
| 测试 | 核心机制使用 Mock LLM 的确定性单元测试覆盖 |
| 记忆系统测试 | 四种合法 MemoryType 枚举验证；未知类型写入被拒绝；中文展示标签到英文枚举的确定性映射；测试失败不被直接固化为跨会话记忆；已验证的失败解决方案可进入 FAILURE_RESOLUTION；tags 不改变 MemoryType；不符合状态/信任要求的记录不自动注入 |
| 离线确定性测试 | 以下核心机制必须使用 ScriptedMockLLM/Fake 组件（MockToolDispatcher、MockMemoryStore、MockCredentialStore、FakeClock）进行确定性测试，不得依赖真实 API Key、真实 LLM 或外部网络：Agent 主循环完整状态转换；工具注册与分发；Guardrail 三级决策（BLOCK/REQUEST_APPROVAL/ALLOW）；审批批准、拒绝、超时及暂停/恢复；反馈分类与回灌；记忆读写和注入边界；配置分层合并；StopPolicy 与无进展检测 |

---

## 12. 风险与未决问题

| 风险 | 影响 | 缓解 |
|------|------|------|
| DeepSeek API 可用性波动 | 本地 LLM 功能中断 | 有 ScriptedMockLLM 可离线测试 |
| Windows 路径逃逸手段多样 | 安全边界被绕过 | 多重规范化 + 执行前再次验证 |
| PyInstaller 打包兼容性 | 分发受阻 | 预留 Docker 作为备选方案 |
| keyring 在无桌面环境不可用 | 本地模式启动失败 | fail closed，明确错误提示 |
| 项目移动后记忆空间变化 | 跨会话记忆失效 | 文档说明，project_id 确定性生成 |
| WebUI 演示无法覆盖所有场景 | 评审误判完整度 | README 说明线上版仅为安全演示 |
| 中国区网络访问 Render | 评审无法访问 WebUI Demo | 可以在 AGENT_LOG 中记录，在本地演示 |

---

## 13. 修订历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.1 | 2026-08-03 | 全面修订：修正状态机（INTERMEDIATE/FINAL_VALIDATION 区分）、ActionKind（TOOL_CALL/COMPLETE_REQUEST）、治理管线（SchemaValidator 前置）、DemoCompositionRoot（Mock 仅外部边界）、补齐 FC 模块规约、补充为 13 个主要数据模型、状态转换矩阵、CI 双系统设计、Open Design 说明、SPEC_PROCESS 完成全部 11 轮记录及总结 |
| 1.1.2 | 2026-08-03 | 全面修正：定义 AgentState 枚举（13 个 AgentState，FINALIZING 为生命周期收尾阶段不计入）；GuardrailResult 去除 approval_request_id（由 ApprovalManager 在 REQUEST_APPROVAL 后创建）；修复 LLMResponse 后重复 cost_used/raw_response 及多余围栏；补齐 UIConfig 等缺失配置模型；WebUI 章节补充 Open Design 版本/skill/产物目录详情及运行依赖声明；区分 WebUI Mock 审批超时（默认 15s/范围 5-60s/超时场景 5s）与本地 CLI 审批（300s）；超时后 TIMEOUT → CANCELLED 动作不执行；FakeClock 测试要求；C3/C4 场景终态修正；C7 覆盖性检查确认；验收标准补充 Demo 安全隔离/浏览器会话隔离/exe 全新环境要求；SPEC_PROCESS/AGENT_LOG 修正 20s/课堂演示错误记录 |
| 1.1.3 | 2026-08-04 | 最终人工审阅修正：§3.8 配置合并规约重写（删除错误交叉引用、增加逐字段确定性合并规则表、解决 tool_timeout 重复、增加 ApprovalConfig）；run_tests/run_typecheck 改为 ALLOW（可信 SensorDefinition 时）；分发要求补充目标平台/架构/签名/SmartScreen/全新环境验收；CI 补充 Windows build-exe job；ToolResult 删除 token_used/cost_used 字段；补充 §7 章节标题；Open Design 改为以仓库内 DESIGN.md 为实现依据、删除 tokens.css 依赖；主要贡献统一为"治理驱动的测试反馈闭环"；验收标准补充离线确定性测试要求 8 项；ROUND_01_HUMAN_DECISIONS.md 文件头修正 |
| 1.1.4 | 2026-08-04 | 最终复审：§3.3 StopPolicy 输入 budget_used 改为 token_used/cost_used；COMPLETED 条件明确仅 FINAL_VALIDATION 状态可达；§3.8 配置合并规则补全（project_root/max_output_tokens/request_timeout/no_progress_threshold/per_tool_timeouts/memory.enabled/cli_timeout）；approval_timeout 分层规则修复（用户级/CLI 5-60s，项目级只能缩短）；cli_timeout 仅用户级/CLI 可设；per_tool_timeouts 逐工具更严格且不超过全局上限；§9.1 Windows build-exe 增加 pytest、SHA-256 写入文件、双 artifact 上传 |