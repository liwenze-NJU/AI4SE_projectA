# SECURITY.md — CodeGuard Harness

## 凭据存储

- 所有 API Key 经 **Windows Credential Manager** 存储（`KeyringCredentialStore`，keyring 库）。
- Key 永不落盘到日志、配置文件、Git 历史或 trace。
- CLI `key set` 使用隐藏输入，不回显。
- CI 环境不使用 Credential Manager，测试套件使用 `MockCredentialStore`。

## 威胁模型

| 威胁 | 缓解措施 |
|------|----------|
| LLM 提议越界文件访问 | `WorkspaceBoundaryRule`（路径规范化 + 多重验证，不可关闭） |
| 危险 Shell 命令 | `CommandWhitelistRule` + `run_process` 结构化 program+args，**从不** `shell=True` |
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
