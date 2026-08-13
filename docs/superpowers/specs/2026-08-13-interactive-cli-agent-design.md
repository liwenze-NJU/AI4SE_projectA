# CodeGuard Interactive CLI Agent Design

## 1. 目标与范围

本增强版将 CodeGuard 从一次性 Harness 会话扩展为可持续文字交互的 Coding Agent。用户在项目目录运行 `codeguard chat --mode local`，输入编程任务后，Agent 可以解释当前行动、读取和搜索代码、修改工作区文件、运行测试，并依据客观反馈继续修复。任务只有在最终验证通过后才能报告完成。

增强版长期保存在 `feature/interactive-cli-agent` 分支，不合并回 `main`。`main` 保留课程提交版 v0.1.1；增强分支可在稳定后创建 `v0.2.0-interactive` 标签或 Release。开发使用 `.worktrees/interactive-cli-agent` 隔离工作树。

第一版采用以下范围：

- 使用 DeepSeek 作为真实 LLM，保留供应商无关的 `LLMClient` 接口。
- 在单个 CLI 进程中支持多轮用户任务和补充说明。
- 自动连续工作；安全只读操作和受信任的测试直接执行，写入或危险动作由现有 Guardrail 决定 ALLOW、REQUEST_APPROVAL 或 BLOCK。
- 完整聊天历史仅保存在当前进程内，退出后消失。
- 现有结构化项目记忆继续支持跨会话存储，但普通聊天和未验证失败不得自动写入。
- 保持现有 Mock Demo、Mock WebUI 和课程验收行为兼容。

第一版不实现流式 Token 输出、完整聊天记录持久化、`/resume`、CLI 内模型切换、真实 WebUI 编程会话、多 Agent 并行、Git push/发布自动化。

## 2. 方案选择

采用渐进式扩展现有 Harness，而不是在外部包装一次性循环或重写第二套 Agent 主循环。

该方案先修复生产组合层，使现有工具、传感器、上下文和记忆真正接入 `AgentLoop`；再增加自然语言消息动作；最后由 `ChatSession` 驱动多个独立任务。这样可以复用既有状态机、Guardrail、审批、反馈和测试资产，同时避免两套循环产生不同的安全语义。

## 3. 总体架构

系统采用两层循环：

```text
ChatSession：管理当前 CLI 进程中的多轮对话
└── AgentLoop：完成一个具体编程任务的治理、工具执行和验证闭环
```

### 3.1 ChatSession

`ChatSession` 负责：

- 读取用户输入并处理斜杠命令；
- 保存当前进程的临时聊天历史和历史任务摘要；
- 为每个新任务创建独立的任务状态和预算；
- 将用户取消与进程退出区分开；
- 把 Agent 事件交给终端输出组件。

`ChatSession` 不直接执行工具或判断动作风险。这些职责继续由 Harness 内核承担。

### 3.2 AgentLoop

`AgentLoop.run_task()` 完成一个用户任务。它复用现有状态机，依次完成上下文构建、模型决策、动作治理、审批、工具执行、反馈回灌、停止判断和最终验证。

每个任务拥有独立的 step、LLM call、Token、费用、时间和无进展预算。任务结束后生成紧凑摘要供当前进程后续对话使用，但不持久化完整 Trace。

为了兼容课程版，现有一次性执行入口可以保留并委托给新的单任务 API；`demo a/b/c` 的行为和终态不得改变。

### 3.3 CompositionRoot

`CompositionRoot` 必须完成真实装配：

- 为文件、补丁和进程工具注册真实处理器，而不是空处理器；
- 注入 `ToolDispatcher`、`SensorRunner`、`ContextBuilder`、记忆存储/检索器、`Tracer` 和 `SecretRedactor`；
- `test` 模式使用确定性 Fake/Mock 外部边界；
- `demo` 模式保持零真实文件、Shell、网络和凭据访问；
- `local` 模式读取 Keyring 中的 DeepSeek 凭据并把当前目录作为工作区根。

### 3.4 CLIEventSink

新增 `CLIEventSink` 接收状态变化、模型消息、工具调用、审批、验证结果和任务终态，并将其格式化为终端文字。Harness 内核不直接散布 `print()`，以便测试输出，也为未来 TUI 或真实 WebUI 保留替换边界。

## 4. 动作模型

动作类型扩展为：

```text
TOOL_CALL         调用已注册工具
ASSISTANT_MESSAGE 向用户解释或报告进展，输出后自动继续决策
REQUEST_USER_INPUT 向用户提出澄清问题并暂停当前任务
COMPLETE_REQUEST  声明当前任务已完成并触发最终验证
```

`ASSISTANT_MESSAGE` 只产生用户可见文字，不暂停、不代表任务完成，也不能绕过最终验证。模型可以先发送说明消息，再继续提出工具动作。

`REQUEST_USER_INPUT` 必须包含一个简短问题，并使任务进入 `AWAITING_USER_INPUT`。用户的下一条普通输入作为该任务的补充上下文，随后恢复 `DECIDING`；输入 `/cancel` 或按 `Ctrl+C` 则以 `CANCELLED` 结束当前任务。第一版不允许在 Agent 正常自动执行工具期间插入普通文字，用户只能在 REPL、审批或 `AWAITING_USER_INPUT` 提示符输入，以避免并发修改任务上下文。

LLM 输出继续使用明确的结构化协议。解析失败时，Harness 将错误作为可恢复反馈要求模型重新输出；重复失败达到阈值后，以 `LIMIT_REACHED` 结束当前任务。

## 5. 任务执行与审批

```text
用户输入任务
→ 构建上下文
→ LLM 返回结构化动作
→ Schema 校验和动作规范化
→ Guardrail 判定
→ 执行、等待审批或阻止
→ 工具结果/测试反馈回灌
→ LLM 继续决策
→ 最终验证
→ 输出任务总结并返回 REPL
```

默认自治策略：

| 动作 | 默认处理 |
| --- | --- |
| 读取普通项目文件、搜索、列目录 | 自动执行 |
| 运行配置中受信任的 pytest、lint、typecheck | 自动执行 |
| 修改普通工作区文件 | 由现有 Guardrail 规则判定 |
| 删除、覆盖或移动文件 | 通常请求审批或阻止 |
| 未注册命令、越界路径、敏感文件访问 | BLOCK |
| Shell 字符串 | 拒绝；只接受结构化 `program + args` |
| Git push、发布或工作区外副作用 | 第一版不支持或默认 BLOCK |

审批请求展示动作、目标、匹配规则和风险摘要。批准只绑定当前 chat session、task、request ID 和 action fingerprint。执行前必须重新校验；批准不能复用于其他动作。

用户拒绝或直接回车时，动作不执行，拒绝结果回灌给模型。模型可以解释、提出安全替代方案或结束任务，但不得以等价动作绕过用户拒绝。

## 6. 上下文与记忆

信息分为三层：

1. **临时聊天历史**：当前进程中的用户请求、Agent 说明和任务总结；退出即删除。
2. **当前任务上下文**：工具调用、Guardrail 结果、测试反馈和剩余预算；任务结束后仅保留摘要。
3. **跨会话结构化记忆**：项目约定、用户批准的决策和已验证解决方案；继续遵循现有状态与信任边界。

上下文构建优先级固定为：

```text
系统安全约束
→ 当前用户任务
→ 最近对话摘要
→ 检索到的可信项目记忆
→ 可用工具及参数格式
→ 最近一次工具/测试/审批结果
→ 当前预算
```

超过上下文预算时，先删除较旧聊天消息，再缩短工具输出。系统约束、当前任务、最新错误、Guardrail/审批结果不得截掉。进入模型上下文的工具输出必须先脱敏、分类和截断，优先保留错误位置、失败摘要、修改文件与重试建议。

## 7. CLI 交互

第一版支持：

| 命令 | 行为 |
| --- | --- |
| `/help` | 显示命令帮助 |
| `/status` | 显示模型、工作区、任务预算和记忆状态，不显示凭据 |
| `/clear` | 清除进程内聊天历史，不删除结构化记忆 |
| `/cancel` | 在审批或等待澄清时取消当前任务；无运行中任务时提示无需取消 |
| `/exit` | 结束 CLI 进程 |
| 普通文字 | 在 REPL 创建新任务，或在 `AWAITING_USER_INPUT` 补充当前任务 |

第一次 `Ctrl+C` 取消当前任务并返回 REPL；没有运行中任务时再次按下或输入 `/exit` 才退出。EOF 视为 `/exit`。

## 8. 错误处理与停止条件

- LLM 超时或临时网络错误：有限次数重试并使用短退避；达到上限后结束当前任务。
- LLM 非法结构化输出：将解析错误回灌；重复失败触发限制终态。
- 工具参数错误或文件不存在：作为可恢复反馈供模型修正。
- Guardrail BLOCK：动作不执行，明确原因回灌。
- 用户拒绝审批：动作不执行，允许模型给出替代方案或解释。
- 工具执行异常：脱敏、分类、回灌；相同失败连续出现达到阈值后停止。
- 必需测试失败：不得报告成功；模型可继续修复直到通过或预算耗尽。
- 凭据、工作区或必需安全组件不可用：fail closed，不启动真实任务。
- 内部异常：终端显示简短错误和 trace ID，完整脱敏信息进入审计 Trace。

任务终态仅包括：

```text
COMPLETED       最终验证通过
FAILED          不可恢复错误
CANCELLED       用户取消
LIMIT_REACHED   步数、Token、费用、时间或无进展阈值耗尽
```

自然语言消息和模型自我声明都不能直接进入 `COMPLETED`。

## 9. 测试设计

实施必须采用 TDD，并补上生产组合根的覆盖缺口。

### 9.1 单元测试

- `ASSISTANT_MESSAGE` 的解析和状态行为；
- `ChatSession` 斜杠命令与进程内历史；
- `REQUEST_USER_INPUT` 的暂停、恢复和取消；
- 上下文优先级、预算截断和脱敏；
- 审批拒绝、取消、非法输出和预算耗尽；
- 完整聊天记录不会写入跨会话 Memory。

### 9.2 生产组合测试

直接创建 `CompositionRoot(mode="test")` 并断言：

- `ToolDispatcher` 和 `SensorRunner` 已装配；
- 标准工具使用真实或明确的 Fake 处理器，不是空 lambda；
- 上下文包含用户任务、工具描述和最新反馈；
- 工具结果实际进入下一次 LLM 调用；
- demo 模式仍无法接触真实组件。

### 9.3 确定性端到端 CLI 测试

使用 `ScriptedMockLLM`、Fake 输入和临时工作区复现：读取文件、说明进展、请求写入审批、批准后真实修改临时文件、首次测试失败、反馈修复、最终测试通过、返回 REPL、执行第二个任务并退出。

另外覆盖审批拒绝、Guardrail BLOCK、`Ctrl+C`、非法模型输出和预算耗尽。

### 9.4 回归和构建验证

- 原有测试全部继续通过；
- `demo a/b/c` 输出和终态不变；
- Mock WebUI 仍不访问真实文件、Shell、网络或凭据；
- Windows EXE 重新构建后执行 CLI、Demo、Key 和 WebUI 冒烟测试；
- CI 在增强分支或长期 Draft PR 上运行，但增强分支不合并到 `main`。

实施前必须重新建立可用的 Python 3.12 开发环境。设计阶段检查发现系统无可用 Python，旧 worktree 的虚拟环境引用了已不存在的解释器，因此当前无法取得新鲜的基线 pytest 结果。

## 10. 实施顺序与版本管理

工作固定在：

```text
branch:   feature/interactive-cli-agent
worktree: .worktrees/interactive-cli-agent
```

实施顺序：

```text
生产组合层接通
→ 工具结果与上下文回灌
→ 对话动作模型
→ ChatSession
→ CLI REPL 与审批交互
→ 确定性端到端测试
→ 文档、Windows 构建和增强版 Release
```

可以创建长期 Draft PR 用于差异审阅和 CI，但不得合并。课程版继续通过 `main` 和 v0.1.1 获取；增强版通过 `feature/interactive-cli-agent` 或后续 `v0.2.0-interactive` 获取。

## 11. 验收标准

在真实项目目录运行 `codeguard chat --mode local` 后：

1. 用户可以连续提交多个编程任务；
2. Agent 能输出文字说明并真正读取、搜索和修改当前工作区；
3. 安全只读工具和受信任测试自动执行；
4. 写入和危险动作严格遵循现有 Guardrail 与审批绑定；
5. 工具结果和测试失败真实回灌并能驱动下一步修复；
6. 只有最终验证通过的任务才进入 `COMPLETED`；
7. `/clear` 只清除进程内历史，`/exit` 后完整聊天记录不保留；
8. 原有课程版 Demo 和 Mock WebUI 保持兼容；
9. 增强版全部修改只存在于增强分支，`main` 保持在课程提交版本。
