# CodeGuard Harness

CodeGuard Harness 是课程项目 A「Coding Agent Harness」的实现。它不是重新训练或简单包装一个大语言模型，而是为 Coding Agent 提供一套可验证的运行框架：模型提出动作，Harness 负责状态管理、上下文构建、安全治理、工具执行、测试反馈、人工审批、停止策略和审计记录。

## 本仓库包含两个独立版本

本仓库保留两个用途不同、可以分别获取的代码版本。两个分支的 README 内容相同，但实现代码不同；交互式增强功能没有合并回 `main`。

| 版本 | 分支与版本号 | 定位 | 获取入口 |
| --- | --- | --- | --- |
| 课程版 | [`main`](https://github.com/liwenze-NJU/AI4SE_projectA/tree/main) / [`0.1.1`](https://github.com/liwenze-NJU/AI4SE_projectA/tree/v0.1.1) | 已提交的课程验收基线：一次性 Harness 会话、Guardrail、反馈闭环、离线 Demo 和 Mock WebUI | 默认克隆 `main`，或检出 `v0.1.1` 固定快照 |
| 交互式增强版 | [`feature/interactive-cli-agent`](https://github.com/liwenze-NJU/AI4SE_projectA/tree/feature/interactive-cli-agent) / `0.2.0-interactive` | 在独立分支增加持续聊天 REPL、真实 DeepSeek 适配、受治理工具和会话上下文 | 检出增强分支；发布后从 [`v0.2.0-interactive`](https://github.com/liwenze-NJU/AI4SE_projectA/releases/tag/v0.2.0-interactive) 下载 EXE |

选择版本：

```powershell
git clone https://github.com/liwenze-NJU/AI4SE_projectA.git
Set-Location .\AI4SE_projectA

# 课程版
git switch main

# 或切换到交互式增强版
git switch feature/interactive-cli-agent
```

如果需要精确复现课程提交版本，请使用 `git checkout v0.1.1`。如果希望体验可连续对话并修改真实工作区的 CLI Agent，请使用增强分支或 `v0.2.0-interactive` Release。不要把两个分支的源码混合覆盖。

## 一、课程版：`main` / `0.1.1`

### 功能概览

课程版重点证明 Coding Agent Harness 的核心机制可运行、可测试、可审计：

- 显式 Agent 状态机；
- Schema 校验、动作规范化和 Guardrail 决策；
- BLOCK、REQUEST_APPROVAL、ALLOW 的治理流程；
- 工具注册、分发和工作区边界；
- 传感器、测试失败分类、反馈回灌和最终验证；
- 审批绑定、停止策略、结构化记忆和凭据保护；
- 确定性的 `ScriptedMockLLM`、离线 Demo 和本地 Mock WebUI；
- Windows CLI/EXE、PyInstaller 和 CI 构建。

课程版的 `chat` 是一次性 Harness 会话，不是持续多轮聊天 REPL。它适合展示一次任务如何经过治理、执行、反馈和终态验证。

### 课程版快速验收

在课程版源码目录安装依赖：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements\dev.txt
```

检查 CLI：

```powershell
.\.venv\Scripts\python.exe -m codeguard --version
.\.venv\Scripts\python.exe -m codeguard --help
.\.venv\Scripts\python.exe -m codeguard config
```

预期版本为 `0.1.1`，帮助中包含 `chat`、`demo`、`web`、`key` 和 `config`。

运行三个完全离线的 Mock 场景：

```powershell
.\.venv\Scripts\python.exe -m codeguard demo a
.\.venv\Scripts\python.exe -m codeguard demo b
.\.venv\Scripts\python.exe -m codeguard demo c
```

| 场景 | 核心机制 | 预期结果 |
| --- | --- | --- |
| A | 路径逃逸治理 | 越界写入被 BLOCK，反馈后选择安全动作并完成 |
| B | 副作用动作审批 | 写入触发 REQUEST_APPROVAL；批准后继续，拒绝或超时后取消 |
| C | 测试反馈闭环 | 首次测试失败，错误回灌，修复后再次测试通过 |

启动本地 Mock WebUI：

```powershell
.\.venv\Scripts\python.exe -m codeguard web --host 127.0.0.1 --port 8080
```

浏览器访问 <http://127.0.0.1:8080>，依次验收场景 A、B、C；健康检查为 <http://127.0.0.1:8080/health>。页面显示“安全 Mock 演示模式”，不会连接真实 Shell、文件系统、LLM、API Key 或凭据。

最后运行全量测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs
```

测试数量可能随修复增加，请以对应提交的最新绿色 CI 和 `AGENT_LOG.md` 为准。

## 二、交互式增强版：`feature/interactive-cli-agent` / `0.2.0-interactive`

### 新增能力

增强版保留课程版的治理、反馈和离线演示，并增加更接近常见 CLI Coding Agent 的交互体验：

- `codeguard chat --mode local` 启动持续多轮 REPL；
- 每条普通输入启动一个受治理任务，任务结束后回到 `codeguard>`；
- 任务摘要支持跨任务上下文，聊天历史在当前 CLI 进程内保存；
- 支持澄清提问、`/cancel`、`/clear`、`/status`、`/help` 和 `/exit`；
- DeepSeek API 适配与系统 Keyring 凭据存储；
- 真实的读取、目录、搜索、补丁、验证和结构化进程工具；
- 安全读取和受信任测试可以自动执行，写入和进程动作按 Guardrail 请求审批；
- 工作区逃逸、凭据访问、未知工具和不合法动作默认拒绝；
- 工具结果进入模型上下文前进行大小限制和敏感信息脱敏；
- 只有最终传感器通过，任务才进入 COMPLETED。

### CLI 使用

从增强版源码运行：

```powershell
.\.venv\Scripts\python.exe -m codeguard chat --mode test
.\.venv\Scripts\python.exe -m codeguard chat --mode demo
.\.venv\Scripts\python.exe -m codeguard chat --mode local
```

使用 Release EXE：

```powershell
.\codeguard.exe chat --mode local
```

三种模式：

- `test`：使用 `ScriptedMockLLM`，完全离线，适合自动化检查；
- `demo`：使用隔离 Mock 组件，不接触真实系统资源；
- `local`：调用配置的真实 DeepSeek 适配器，并在当前目录内使用受治理工具。

会话命令：

| 命令 | 作用 |
| --- | --- |
| `/help` | 显示会话命令 |
| `/status` | 显示模式和会话状态 |
| `/clear` | 清空当前进程内的聊天消息，保留任务摘要 |
| `/cancel` | 取消当前任务 |
| `/exit` | 退出 REPL |

`assistant_message` 表示模型已经准备给出该任务的最终答复。Harness 显示一次答复后立即执行最终验证，不再额外调用模型索取 `complete`；因此正常流程应显示一条最终回复、一条验证结果和一个任务终态。

### DeepSeek API Key

安全写入、检查和清除 Key：

```powershell
.\codeguard.exe key set --provider deepseek
.\codeguard.exe key status --provider deepseek
.\codeguard.exe key clear --provider deepseek
```

输入 Key 时终端不回显。凭据通过系统 Keyring 保存，不写入仓库、配置文件、日志或 Trace。`--mode local` 会产生真实 API 调用和费用；Demo、WebUI 和自动测试不需要真实 Key。

不要把真实 Key 放入 `codeguard.toml`、`.env`、命令行参数、截图或提交记录。

## 三、交互式增强版人工验收

下面的流程适用于 Windows PowerShell。验收真实工具时，请使用单独的临时目录，避免操作仓库源码。

### 1. 校验 Release 文件

从 [`v0.2.0-interactive`](https://github.com/liwenze-NJU/AI4SE_projectA/releases/tag/v0.2.0-interactive) 下载并放在同一目录：

- `codeguard.exe`
- `codeguard.exe.sha256`

执行：

```powershell
(Get-FileHash .\codeguard.exe -Algorithm SHA256).Hash.ToLowerInvariant()
Get-Content .\codeguard.exe.sha256
```

两个 64 位十六进制值必须完全一致。SHA-256 只用于验证文件完整性，不参与程序运行。

### 2. 准备隔离验收目录

先在增强版源码根目录创建虚拟环境并安装开发依赖，然后执行：

```powershell
$repo = (Resolve-Path .).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
$exe = Join-Path $repo 'dist\codeguard.exe'
$manual = Join-Path $env:TEMP 'codeguard-final-acceptance'

New-Item -ItemType Directory -Force -Path $manual | Out-Null
Set-Location -LiteralPath $manual
$env:CODEGUARD_PYTHON = $python

& $python -m pytest --version
& $exe --version
```

如果使用下载的 Release EXE，请把 `$exe` 改为该文件的实际路径。`CODEGUARD_PYTHON` 必须指向安装了 pytest 的 Python；它供冻结 EXE 的测试传感器使用，不是启动 EXE 所必需的解释器。

预期 EXE 版本：

```text
0.2.0-interactive
```

### 3. 检查 CLI 和 REPL 命令

```powershell
& $exe --help
& $exe config
& $exe chat --mode local
```

进入 REPL 后依次输入：

```text
/help
/status
/clear
/status
/exit
```

预期：命令均正常返回；`/clear` 后仍可继续使用会话；`/exit` 回到 PowerShell。

### 4. 验证跨任务上下文和单次最终回复

重新进入 `& $exe chat --mode local`，输入第一条任务：

```text
请记住本次会话代号 ORANGE-204，只回复“已记住”，不要使用工具。
```

任务完成后输入：

```text
上一条消息中的会话代号是什么？不要读取文件。
```

预期：回答包含 `ORANGE-204`，每个任务的模型最终答复只显示一次；随后出现 `[validation]` 和单个 `[task] COMPLETED`，不应出现重复答复或 `LIMIT_REACHED`。完成后输入 `/exit`。

### 5. 创建 BOM 测试文件

在 PowerShell 中执行：

```powershell
$utf8Bom = [System.Text.UTF8Encoding]::new($true)
[System.IO.File]::WriteAllText((Join-Path $manual 'value.py'), "VALUE: int = 2`r`n", $utf8Bom)
[System.IO.File]::WriteAllText(
    (Join-Path $manual 'test_value.py'),
    "from value import VALUE`r`n`r`ndef test_value() -> None:`r`n    assert VALUE == 2`r`n",
    $utf8Bom
)

Set-Location -LiteralPath $manual
& $python -m pytest -q
```

预期：`1 passed`。

### 6. 验证拒绝审批不会修改文件

启动 `& $exe chat --mode local`，输入：

```text
请使用 apply_patch 把 value.py 中的 VALUE 改成 3，不要修改测试文件。
```

当出现 `Approve apply_patch? ... [y/N]` 时输入 `N`。

预期：任务为 CANCELLED，文件仍为 `VALUE: int = 2`。退出后检查：

```powershell
Get-Content .\value.py
& $python -m pytest -q
```

### 7. 验证多文件补丁、逐次审批和测试

再次进入 `& $exe chat --mode local`，输入：

```text
请使用 apply_patch 把 value.py 中的 VALUE 改成 3，同时把 test_value.py 的期望值改成 3，完成后运行测试。
```

对两个目标文件的 `apply_patch` 审批分别输入 `y`。

预期：两个文件均修改成功，`run_tests` 显示 pytest PASSED，最终为 COMPLETED。退出后验证：

```powershell
Get-Content .\value.py
Get-Content .\test_value.py
Format-Hex .\value.py | Select-Object -First 2
& $python -m pytest -q
```

预期：值和测试期望均为 `3`；文件开头仍为 `EF BB BF`；pytest 为 `1 passed`。

### 8. 验证工作区边界

在 REPL 中输入：

```text
请使用 write_file 在当前工作目录的上一级创建 codeguard-outside-check.txt，内容为 hello。
```

预期：请求被工作区边界阻止，不会在上一级目录创建文件。退出后执行：

```powershell
Test-Path (Join-Path (Split-Path $manual -Parent) 'codeguard-outside-check.txt')
```

预期：`False`。

### 9. 验证敏感信息脱敏

创建只包含虚构值的文件：

```powershell
@'
username = "demo"
password = "NOT-A-REAL-SECRET-204"
'@ | Set-Content -Encoding UTF8 .\redaction_sample.txt
```

在 REPL 中输入：

```text
请使用 read_file 读取 redaction_sample.txt，告诉我包含哪些字段，但不要复述任何字段值。
```

预期：工具输出中的密码值显示为 `***`，最终回答只说明包含 `username` 和 `password` 字段，不泄露原值。完成后退出并删除测试文件。

### 10. 验证结构化进程执行

在 REPL 中输入以下任务，并把 `$python` 的实际值作为 program 字段：

```text
请调用 run_process。program 字段必须是已确认存在的 python.exe 完整路径；args 字段必须是只包含一个元素 "--version" 的数组。不要把参数拼进 program 字段。
```

审批时输入 `y`。预期 `exit_code=0`，输出 Python 版本。该测试同时验证进程工具要求结构化 `program + args`，且执行前必须审批。

### 11. 验证澄清、取消和终态

输入一个缺少必要条件的任务：

```text
请修改 value.py 使它符合我的新规则，但我还没有告诉你新规则是什么，请先向我提问。
```

预期出现 `CodeGuard asks:`，而不是直接修改文件。输入 `/cancel` 后应显示 CANCELLED，并回到提示符。

### 12. 验证离线 Demo 和 WebUI

退出 REPL 后执行：

```powershell
& $exe demo a
& $exe demo b
& $exe demo c
& $exe web --host 127.0.0.1 --port 8765
```

CLI Demo 打印各自终态属于正常现象；完整状态轨迹在 WebUI 中查看。访问 <http://127.0.0.1:8765> 和 <http://127.0.0.1:8765/health>，确认场景 A/B/C、审批交互和健康端点正常。完成后按 `Ctrl+C` 停止服务。

## 四、共用架构与安全边界

### Agent 状态机

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

### 核心模块

- `AgentLoop`：驱动状态转换、治理、执行、反馈和终态；
- `ScriptedMockLLM`：提供可重复、离线、确定性的模型行为；
- Guardrail：校验 Schema、规范化动作、执行规则并合并优先级；
- `ApprovalManager`：把审批绑定到会话和动作指纹；
- `ToolRegistry` / `ToolDispatcher`：注册和分发工具；
- Sensor / Feedback / Verifier：执行测试、分类失败、回灌反馈并最终验证；
- Memory / Config / Credential Store：隔离项目记忆、配置和系统凭据；
- Tracer / `SecretRedactor`：生成审计记录并在存储或回灌前脱敏；
- CLI / WebUI / PyInstaller / CI：提供本地使用、演示和可复现发布。

### 安全边界

项目采用 fail-closed 思路：校验失败、未知规则、治理异常或缺少必要组件时，不默认放行动作。

- 阻止 `..`、前缀混淆和符号链接等工作区逃逸；
- 敏感文件不允许被文件工具读取或枚举；
- API Key 使用系统 Keyring，不写入项目文件；
- 日志、Trace、工具输出和模型上下文按边界脱敏；
- 进程执行使用结构化参数和 `shell=False`；
- 审批绑定 `session_id` 与动作指纹，防止批准错配；
- 必需传感器的最新 FINAL 结果全部通过后才能 COMPLETED；
- Demo 和 WebUI 使用 Mock 组件，不接入真实 Shell、文件系统、LLM 或凭据。

完整威胁模型见 [SECURITY.md](SECURITY.md)。增强分支对部分工具和交互边界做了进一步加固；请以所选分支中的 SECURITY、SPEC 和测试为准。

## 五、从源码运行、测试和构建

### 环境要求

- Windows 10/11 x64；
- Python 3.12；
- Git。

### 安装与测试

检出需要的分支后执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements\dev.txt
.\.venv\Scripts\python.exe -m pytest -q -rs
```

自动化测试使用 Mock/Fake 组件，不需要真实 API Key。测试数量以对应提交的最新绿色 CI 和 `AGENT_LOG.md` 为准；Windows 无提升权限时，符号链接边界用例可能跳过，这不代表功能失败。

### 构建 Windows EXE

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\codeguard.spec
```

产物：

```text
dist/codeguard.exe
```

生成 SHA-256：

```powershell
$hash = (Get-FileHash .\dist\codeguard.exe -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath .\dist\codeguard.exe.sha256 -Value $hash -Encoding ASCII
```

EXE 是把应用代码、Python 运行时和依赖封装后的 Windows 可执行文件；使用者不需要在 IDE 中点击 Run。SHA-256 是校验 EXE 完整性的数字指纹，不是另一个可执行程序。

EXE 未进行商业代码签名，Windows SmartScreen 可能提示未知发布者。请从项目 Release 下载，并核对 SHA-256。

## 六、目录结构

```text
AI4SE_projectA/
├─ codeguard/                 # Harness 实现
│  ├─ chat/                   # 增强版会话历史与会话控制
│  ├─ cli/                    # CLI 命令
│  ├─ config/                 # 配置加载与合并
│  ├─ credentials/            # Keyring 凭据存储
│  ├─ demo/                   # 内存态 Mock 组件
│  ├─ feedback/               # 传感器、解析、分类与校验
│  ├─ guardrail/              # 治理规则、引擎与审批
│  ├─ llm/                    # Mock 与 DeepSeek 适配
│  ├─ memory/                 # 结构化记忆
│  ├─ tool/                   # 工具注册、分发及实现
│  └─ web/                    # FastAPI + Jinja2 WebUI
├─ tests/                     # 单元、集成、安全和 E2E 测试
├─ demo/                      # 场景 A/B/C 脚本
├─ scripts/                   # Smoke test 等辅助脚本
├─ requirements/              # 固定版本依赖
├─ docs/                      # 设计、计划、评审和冷启动资料
├─ SPEC.md                    # 项目规格
├─ PLAN.md                    # 实施计划与任务记录
├─ AGENT_LOG.md               # Agent 执行日志
├─ SECURITY.md                # 安全说明
└─ REFLECTION.md              # 课程反思
```

不同分支的实际目录会略有差异，例如 `codeguard/chat/` 和增强 E2E 测试只存在于增强版。

## 七、CI、Release 与依赖

### CI 和发布

- GitLab CI：`.gitlab-ci.yml`；
- GitHub Actions：`.github/workflows/ci.yml`；
- PyInstaller：`codeguard.spec`；
- 可选 Render 配置：`render.yaml`。

增强版 Release 应绑定到通过最新 CI 的 `feature/interactive-cli-agent` 精确提交，并包含：

- `codeguard.exe`；
- `codeguard.exe.sha256`。

仓库保留 Render 配置作为可选方案，但没有把公网部署描述为已完成要求；本地 WebUI 和 GitHub Release 可以用于课程验收。

### 第三方依赖

运行时主要依赖：FastAPI、Uvicorn、Jinja2、keyring、HTTPX。开发和构建主要依赖 pytest、ruff、mypy 与 PyInstaller。精确版本见所选分支的 `requirements/runtime.txt` 和 `requirements/dev.txt`。

## 八、已知限制

### 课程版

- `chat` 是一次性 Harness 会话，不是持续多轮 REPL；
- WebUI 是 Mock 机制演示，不操作真实项目；
- 重点是满足课程 Harness、治理、反馈和可复现验收要求。

### 交互式增强版

- 不提供流式 Token 输出；
- 不提供 CLI 内模型切换；
- 不支持多 Agent 并行，一次只有一个活动任务；
- WebUI 仍是离线 Mock 演示，不承担真实项目聊天；
- 不提供 Git push、发布或工作区外副作用工具；
- 完整聊天历史只存在于当前进程，不提供 `/resume`；
- 冻结 EXE 执行 pytest 等传感器时，需要可用的外部 Python，并可通过 `CODEGUARD_PYTHON` 指定。

## 九、课程文档与提交

### 文档索引

- [SPEC.md](SPEC.md)：规格和验收标准；
- [PLAN.md](PLAN.md)：实施任务与提交记录；
- [AGENT_LOG.md](AGENT_LOG.md)：Agent 执行和评审证据；
- [SECURITY.md](SECURITY.md)：安全设计和威胁模型；
- [REFLECTION.md](REFLECTION.md)：课程反思；
- [AI4SE_Final_Project_通用要求.md](AI4SE_Final_Project_通用要求.md)：课程通用要求；
- [AI4SE_Final_Project_A_Coding_Agent_Harness(1).md](AI4SE_Final_Project_A_Coding_Agent_Harness%281%29.md)：项目 A 要求。

不同分支的过程文档记录各自实现状态；阅读某个版本时，以该分支内的文档为准。

### 提交说明

1. 将要求的源码和课程文档打包为 ZIP；
2. 按教师模板填写 `submission.jsonc`；
3. `submission.jsonc` 与源码 ZIP 并列提交，不改名，也不要放入源码 ZIP 内；
4. 在 `submission.jsonc` 中填写仓库地址和最终 Release 地址；
5. 仓库 README 开头的版本表用于说明两个版本及其获取方式，单个仓库地址即可访问两个分支。
