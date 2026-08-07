# CodeGuard Harness

CodeGuard Harness 是课程项目 A「Coding Agent Harness」的实现。项目重点不在于重新训练或包装一个大语言模型，而在于实现一套可验证的 Agent 运行框架：模型提出动作，Harness 负责状态管理、上下文构建、安全治理、工具执行、测试反馈、人工审批、停止策略和审计记录。

本仓库同时提供两种本地入口：

- Windows CLI / EXE：运行离线演示、一次性 Harness 会话、API Key 管理和 WebUI。
- 本地 WebUI：以确定性的 Mock 数据逐步展示 BLOCK、人工审批和测试失败修复闭环。

> 面向老师和助教：如果只想快速验收，请直接阅读下一节「5 分钟验收指南」。

## 5 分钟验收指南

### 1. 获取发布文件

正式发布后，可在 [GitHub Releases](https://github.com/liwenze-NJU/AI4SE_projectA/releases) 下载：

- `codeguard.exe`
- `codeguard.exe.sha256`

当前构建目标为 Windows x64。下载后请将两个文件放在同一目录。

### 2. 校验文件完整性

在该目录打开 PowerShell，执行：

```powershell
Get-FileHash .\codeguard.exe -Algorithm SHA256
Get-Content .\codeguard.exe.sha256
```

两处 SHA-256 值应完全一致。Windows 也可以使用：

```cmd
certutil -hashfile codeguard.exe SHA256
type codeguard.exe.sha256
```

### 3. 检查 CLI

```cmd
codeguard.exe --help
codeguard.exe --version
codeguard.exe config
```

预期结果：命令正常退出，版本为 `0.1.0`，帮助中包含 `chat`、`demo`、`web`、`key` 和 `config`。

### 4. 验收三个离线场景

```cmd
codeguard.exe demo a
codeguard.exe demo b
codeguard.exe demo c
```

三个场景均不访问真实网络、文件系统、Shell、LLM 或凭据：

| 场景 | 核心机制 | 预期观察 |
| --- | --- | --- |
| A | 路径逃逸治理 | 越界 `write_file` 被 BLOCK，反馈后安全动作被 ALLOW，最后完成 |
| B | 副作用动作审批 | `write_file` 触发 REQUEST_APPROVAL；批准后继续，拒绝或超时后进入 CANCELLED |
| C | 测试反馈闭环 | 第一次测试失败，错误被分类并回灌，修复后再次测试通过并完成 |

CLI 演示会打印最终终态；更完整的状态转换、护栏决定和反馈轨迹请在 WebUI 中查看。

### 5. 验收本地 WebUI

```cmd
codeguard.exe web
```

浏览器打开 <http://127.0.0.1:8080>，依次进入场景 A、B、C，并使用「步进」「重放」和审批按钮观察状态变化。WebUI 顶部始终显示「安全 Mock 演示模式」，表示它不会连接真实 Shell、文件系统、LLM、API Key 或凭据。

可额外检查健康端点：<http://127.0.0.1:8080/health>。完成后在启动 WebUI 的终端中按 `Ctrl+C` 停止服务。

## 项目实现了什么

CodeGuard 将一次 Agent 会话组织为显式状态机。主要流程如下：

```text
INITIALIZING
  -> BUILDING_CONTEXT
  -> DECIDING
  -> GOVERNING
  -> AWAITING_APPROVAL（需要时）
  -> EXECUTING
  -> INTERMEDIATE_VALIDATION
  -> FEEDING_BACK
  -> FINAL_VALIDATION
  -> COMPLETED / FAILED / CANCELLED / LIMIT_REACHED
```

主要模块包括：

- `AgentLoop`：驱动状态转换和一次性 Harness 会话。
- `ScriptedMockLLM`：提供可重复、离线、确定性的测试模型。
- Guardrail 管线：Schema 校验、动作规范化、规则执行和优先级合并。
- ApprovalManager：将审批请求绑定到会话和动作指纹，支持批准、拒绝与超时。
- ToolRegistry / ToolDispatcher：注册、查找并分发文件与进程工具。
- SensorRunner / FeedbackClassifier / ObjectiveVerifier：执行传感器、分类失败、回灌反馈并进行最终校验。
- Memory / Config / Credential Store：提供项目隔离记忆、配置合并和系统凭据存储。
- Tracer / SecretRedactor：记录审计事件，并在存储前脱敏。
- CLI、WebUI、PyInstaller、CI 配置和离线演示脚本。

## CLI 使用说明

### 命令总览

```cmd
codeguard.exe --help
```

| 命令 | 用途 |
| --- | --- |
| `chat` | 运行一次 Harness 会话 |
| `demo` | 运行离线 Mock 场景 A/B/C |
| `web` | 启动本地 Mock WebUI |
| `key` | 安全设置、检查、更新或清除 API Key |
| `config` | 显示当前有效配置 |

### 一次性 Harness 会话

```cmd
codeguard.exe chat --mode test
codeguard.exe chat --mode demo
codeguard.exe chat --mode local
```

三种模式的含义：

- `test`：使用 `ScriptedMockLLM`，完全离线，适合自动化验证。
- `demo`：使用隔离的 Mock 演示环境，不接触真实系统资源。
- `local`：使用本地配置和已保存的 DeepSeek 凭据，允许走真实模型适配器路径。

`chat` 当前表示「运行一次 Harness 会话」，成功时输出类似：

```text
Session completed: completed
```

它不是持续多轮聊天 REPL，也不会逐字流式显示模型回答。课程版优先实现并验证了 Harness 的治理、反馈和终态判定。

### API Key 管理

先检查状态：

```cmd
codeguard.exe key status --provider deepseek
```

安全写入 API Key：

```cmd
codeguard.exe key set --provider deepseek
```

程序会交互式提示输入，输入内容不会回显，也不会作为命令行参数出现在历史记录中。凭据通过系统 Keyring 后端保存，不写入仓库、配置文件或日志。

更新与清除：

```cmd
codeguard.exe key update --provider deepseek
codeguard.exe key clear --provider deepseek
```

安全建议：

- 不要把真实 Key 写进 `codeguard.toml`、`.env`、截图或提交记录。
- 演示与自动化测试不需要真实 Key。
- 只有明确测试 `local` 模式时才配置 Key；测试完成后可立即清除。
- 真实 API 调用可能产生第三方费用，请先确认账户余额和计费规则。

## WebUI 使用说明

启动：

```cmd
codeguard.exe web
```

指定监听地址或端口：

```cmd
codeguard.exe web --host 127.0.0.1 --port 8080
```

WebUI 是 Harness 工作机制的可视化验收界面，而不是通用聊天网页。它提供：

- 场景选择页；
- 状态机时间线；
- 执行轨迹、工具调用和护栏决定；
- 场景 B 的审批交互；
- 场景 C 的失败分类、反馈回灌和修复后通过；
- 重放和会话隔离。

WebUI 使用内存态 Mock 会话。页面中出现的路径、工具结果、审批和测试结果都是确定性演示数据，不会修改教师机器上的真实文件。

## 从源码运行与测试

### 环境要求

- Windows 10/11 x64
- Python 3.12
- Git

### 获取源码

```cmd
git clone https://github.com/liwenze-NJU/AI4SE_projectA.git
cd AI4SE_projectA
```

### 创建环境并安装依赖

```cmd
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements\dev.txt
```

### 运行测试

```cmd
python -m pytest -q -rs
```

本 README 重写前的最新本地验证结果为：

```text
626 passed, 1 skipped
```

唯一跳过项是 Windows 环境在无提升权限时无法创建符号链接的边界测试；它不是功能失败。所有测试均使用 ScriptedMockLLM / MockToolDispatcher / MockMemoryStore / MockCredentialStore / FakeClock，无真实 LLM、无网络、无 API Key。

### 从源码运行 CLI

```cmd
python -m codeguard --help
python -m codeguard demo a
python -m codeguard web
```

## 构建 Windows EXE

安装开发依赖后执行：

```cmd
pyinstaller --clean --noconfirm codeguard.spec
```

产物位于：

```text
dist/codeguard.exe
```

生成校验值：

```powershell
(Get-FileHash .\dist\codeguard.exe -Algorithm SHA256).Hash.ToLower() |
  Set-Content .\dist\codeguard.exe.sha256
```

EXE 未进行商业代码签名，Windows SmartScreen 可能显示未知发布者提示。请优先从仓库 Release 页面下载，并核对 SHA-256。

## 目录结构

```text
AI4SE_projectA/
├─ codeguard/                 # Harness 实现
│  ├─ cli/                    # CLI 命令
│  ├─ config/                 # 配置加载与合并
│  ├─ credentials/            # Keyring 凭据存储
│  ├─ demo/                   # 内存态 Mock 组件
│  ├─ feedback/               # 传感器、解析、分类与校验
│  ├─ guardrail/              # 治理规则、引擎与审批
│  ├─ llm/                    # LLM 协议、Mock 与 DeepSeek 适配器
│  ├─ memory/                 # JSON 记忆与检索
│  ├─ tool/                   # 工具注册、分发及实现
│  └─ web/                    # FastAPI + Jinja2 WebUI
├─ tests/                     # 单元、集成、安全和 Web 测试
├─ demo/                      # 场景 A/B/C 可执行脚本
├─ scripts/                   # Smoke test 等辅助脚本
├─ requirements/              # 固定版本依赖
├─ docs/                      # 设计、冷启动与过程资料
├─ dist/                      # 本地构建产物（Release 时上传）
├─ SPEC.md                    # 项目规格
├─ PLAN.md                    # 实施计划与任务记录
├─ AGENT_LOG.md               # Agent 执行日志
├─ SECURITY.md                # 安全说明
└─ REFLECTION.md              # 课程反思
```

## 安全边界

项目采取 fail-closed 思路：校验失败、未知规则结果、治理异常或缺少必要组件时，不应默认放行动作。

关键边界包括：

- 工作区边界：阻止 `..`、前缀混淆和符号链接等路径逃逸。
- 凭据保护：敏感文件不允许被文件工具读取或枚举；API Key 使用系统 Keyring。
- 输出脱敏：日志和 Trace 在存储前使用 `SecretRedactor` 处理。
- 命令执行：`shell=False`，并限制工作目录和危险元字符。
- 审批绑定：请求绑定 `session_id` 和动作指纹，防止批准错配。
- 最终校验：只有必需传感器的最新 FINAL 结果全部通过，才能进入 COMPLETED。
- 演示隔离：WebUI 与场景 A/B/C 使用 Mock 组件，不接入真实 Shell、文件系统、LLM 或凭据。

更完整的威胁模型和边界说明见 [SECURITY.md](SECURITY.md)。

## CI、发布与部署

- GitLab CI：`.gitlab-ci.yml`
- GitHub Actions：`.github/workflows/ci.yml`
- PyInstaller 配置：`codeguard.spec`
- 可选 Render 配置：`render.yaml`

课程交付采用 GitHub Release：上传 `codeguard.exe` 和 `codeguard.exe.sha256`，教师可直接下载 CLI，并通过 `codeguard.exe web` 启动本地 WebUI。

仓库中保留了 Render 配置作为可选部署方案，但本项目当前没有声明已完成公网部署，也不会提供虚假的部署 URL。

## 第三方依赖

运行时依赖：

- [FastAPI](https://fastapi.tiangolo.com/)：Web API
- [Uvicorn](https://www.uvicorn.org/)：ASGI 服务
- [Jinja2](https://jinja.palletsprojects.com/)：HTML 模板
- [keyring](https://pypi.org/project/keyring/)：系统凭据存储
- [HTTPX](https://www.python-httpx.org/)：DeepSeek HTTP 适配器

开发与构建依赖：

- [pytest](https://docs.pytest.org/)：自动化测试
- [PyInstaller](https://pyinstaller.org/)：Windows EXE 打包

精确版本见 `requirements/runtime.txt` 和 `requirements/dev.txt`。这些第三方项目分别遵循其上游许可证；本仓库未复制第三方项目源码。

## 已知限制与后续方向

课程版的目标是证明 Harness 核心机制可运行、可测试、可审计，因此当前存在以下明确限制：

- `chat` 是一次性 Harness 会话，不是持续多轮聊天 REPL。
- 不提供模型选择菜单、流式回复或长对话历史界面。
- WebUI 仅用于离线 Mock 机制演示，不直接操作真实项目。
- Windows EXE 未签名，可能触发 SmartScreen。
- 当前构建和人工验收以 Windows x64 为主，其他平台需从源码运行并自行验证。
- Render 公网部署为可选项，尚未实际执行。

受课程提供的模型/API Token 额度限制，本项目把有限预算优先投入到状态机、治理护栏、审批、工具安全、反馈闭环、确定性 Mock、自动化测试和可复现交付上。持续聊天、模型切换、流式输出等实用体验未在本次课程交付中继续扩展。这不影响课程要求中的 Harness 核心机制与演示；后续若继续开发，可在新分支中增加多轮会话、模型配置、流式响应、持久化 WebUI 和更完整的真实项目执行体验。

## 课程文档索引

- [SPEC.md](SPEC.md)：最终规格与验收标准
- [PLAN.md](PLAN.md)：实施任务和提交记录
- [AGENT_LOG.md](AGENT_LOG.md)：Agent 执行与评审记录
- [SECURITY.md](SECURITY.md)：安全设计和威胁模型
- [REFLECTION.md](REFLECTION.md)：课程反思
- [AI4SE_Final_Project_通用要求.md](AI4SE_Final_Project_通用要求.md)：课程通用要求
- [AI4SE_Final_Project_A_Coding_Agent_Harness(1).md](AI4SE_Final_Project_A_Coding_Agent_Harness%281%29.md)：项目 A 要求

## 提交说明

课程提交时：

1. 将源码和要求文档打包提交到 selearning。
2. 按教师模板填写 `submission.jsonc`。
3. `submission.jsonc` 与源码压缩包并列提交，不改名，也不要放入源码压缩包内部。
4. 创建 GitHub Release 后，在 `submission.jsonc` 中填写仓库链接和 Release 链接。
