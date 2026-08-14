# SECURITY.md — CodeGuard Harness

## 增强版安全说明（feature/interactive-cli-agent）

以下条目仅适用于增强分支 `feature/interactive-cli-agent`（`codeguard chat` 交互式会话）。课程版 `main` / v0.1.1 不包含交互式会话。增强分支未合并回 `main`。

- **澄清输入（REQUEST_USER_INPUT）**：模型需要补充信息时，任务进入 `AWAITING_USER_INPUT` 并暂停；只有用户的下一条普通输入会作为该任务的补充上下文注入。Agent 自动执行期间用户无法插入普通文字（只能通过 REPL、审批或澄清提示符），避免并发修改任务上下文。
- **审批绑定**：写入/危险动作的审批请求绑定 `session_id` + 动作指纹（`request + action fingerprint`），批准结果不能跨会话或跨动作复用；空输入、`n`、Ctrl+C 均视为拒绝，任务进入 CANCELLED。
- **有界上下文**：进入模型上下文的聊天历史有明确上限（50 条消息 + 10 条任务摘要）；上下文预算超限时先删除较旧聊天消息，再截短工具输出；系统约束、当前任务、最新错误、Guardrail/审批结果不得截掉；所有工具输出先脱敏、分类、截断再进入上下文。
- **受信任的验证工具**：`run_tests` / `run_lint` / `run_typecheck` 由运行配置定义（固定命令、超时、schema 不可由模型指定参数），只能运行配置声明的验证命令；模型不可用它执行任意命令。`run_process` 属于危险动作，必须审批。
- **取消语义**：`/cancel` 取消当前任务（无运行任务时仅提示）；任务内 Ctrl+C 等同取消并返回 REPL；空闲 REPL 的 Ctrl+C 以退出码 130 退出；EOF 视为 `/exit`。取消不写结构化记忆（当前循环设计中 `AgentLoop` 与 `ChatSession` 没有任何记忆写入调用；记忆存储 API 仅提供审批门控的 `propose_write` + `approve_memory`/`reject_memory`），不留完整聊天文件。
- **禁止 push/发布工具**：第一版不提供 Git push、发布或工作区外副作用工具；相关工具未注册（default-deny BLOCK）。`run_process` 属危险动作必须审批（`ToolRiskRule` 按工具声明风险返回 REQUEST_APPROVAL），并以结构化 program+args（**从不** `shell=True`）、参数元字符拒绝（`` ;&|`$ `` 出现在 args 中即拒绝）和 cwd 限制在工作区内三重约束收紧，不能绕过。

## 凭据存储

- 所有 API Key 经 **Windows Credential Manager** 存储（`KeyringCredentialStore`，keyring 库）。
- Key 永不落盘到日志、配置文件、Git 历史或 trace。
- CLI `key set` 使用隐藏输入，不回显。
- CI 环境不使用 Credential Manager，测试套件使用 `MockCredentialStore`。

## 威胁模型

| 威胁 | 缓解措施 |
|------|----------|
| LLM 提议越界文件访问 | `WorkspaceBoundaryRule`（路径规范化 + 多重验证，不可关闭） |
| 危险 Shell 命令 | `run_process` 须审批（`ToolRiskRule` REQUEST_APPROVAL）+ 结构化 program+args（`shell=False`）+ 参数元字符拒绝（`` ;&|`$ ``）+ cwd 限制在工作区内 |
| 凭据泄露进 LLM 上下文/trace | `CredentialLeakRule` + 统一 `SecretRedactor` 覆盖所有数据路径 |
| 未注册工具/未知动作 | `UnregisteredToolRule` + 默认拒绝（default-deny）——无规则匹配即 BLOCK |
| 审批复用 | 审批绑定具体 Action（session + request + action fingerprint），不可复用 |
| 模式越权 | `ModeRestrictionRule`（demo 模式禁止真实执行边界） |
| 输出注入 | 所有工具输出经大小限制 + `SecretRedactor` 后才进入 trace/LLM 上下文 |

## Fail-Closed 策略

- 配置错误 → **fail closed**，给出明确错误提示，不自动回退。
- 凭据存储不可用 → **fail closed**，报错退出。
- 无规则匹配的动作 → **BLOCK**（default-deny）。
- 未配置的模式/边界 → 拒绝执行。

## SecretRedactor

`codeguard/secret.py` 在存储前对所有输出统一脱敏（按序执行）：

1. `sk-` API Key：保留 `sk-` 前缀，遮蔽 key 主体（`sk-***`）
2. 通用凭据字段（`api_key=`、`password=`、`secret=`、`token=`）：值脱敏为 `***`
3. 工作区根路径：替换为 `.`（可移植性）
4. 长度限制：超过 `max_length` 截断并追加 `...[truncated]`

应用路径：日志、trace、ToolResult、Feedback、Memory 注入前、LLM 上下文。

## Demo 隔离

- WebUI demo 模式（`MODE=demo`）运行**真实 Harness 核心**，外部边界全部 Mock：
  `ScriptedMockLLM` / `MockToolDispatcher` / `MockMemoryStore` / `MockCredentialStore` /
  `FakeClock`，无真实 LLM、Shell、文件系统、网络或 Credential Manager。
- `DemoCompositionRoot` **不导入** `DeepSeekAdapter`、`KeyringCredentialStore`、
  `LocalToolExecutor` 或网络客户端；即使环境中存在 API Key 或真实配置也不读取。
- 浏览器会话隔离：不同浏览器 session 使用独立 session_id 与独立内存状态。

## SmartScreen 说明

`dist\codeguard.exe` **未签名**（无代码签名证书），Windows SmartScreen 可能提示
"Windows 已保护你的电脑 / 未知发布者"。这是预期行为：

- 点击"更多信息 → 仍要运行"放行；或使用 `certutil -hashfile dist\codeguard.exe SHA256`
  与发布方提供的 `codeguard.exe.sha256` 比对，确认文件完整性。
- 仅从受信渠道（CI artifact、发布者直发）获取 exe，校验哈希后再运行。

## CI 安全约束

- CI 不访问真实 LLM、外部业务 API 或真实凭据。
- 不配置任何真实 API Key 或 Secrets。
- 不访问 Windows Credential Manager（CI 环境不可用）。
- 不输出、上传或缓存凭据相关文件。
- DeepSeek 连通性脚本为手动触发，**不在 CI 中自动运行**。
