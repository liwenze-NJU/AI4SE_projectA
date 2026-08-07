# CodeGuard Harness

治理驱动的 Coding Agent 测试反馈闭环（AI4SE Final Project A）。

CodeGuard Harness 是一个从零实现的 Python 3.12 CLI Coding Agent Harness（Windows），
核心机制全部以**代码**实现而非提示词约束：

- **治理护栏（Guardrail）**：默认拒绝（default-deny）策略，未注册工具与未知动作一律 BLOCK；
  内置不可关闭规则（工作区边界、凭据泄露、未注册工具、模式限制）；三级决策
  **BLOCK / REQUEST_APPROVAL / ALLOW**；审批与具体 Action 绑定，不可复用。
- **测试反馈闭环（Feedback Loop）**：SensorRunner 驱动 pytest/ruff/mypy 等确定性传感器，
  三层分类（执行状态 → 失败类别 → 诊断详情），`failure_fingerprint` 识别重复失败，
  反馈回灌 LLM 驱动自我修正，全部传感器 PASSED 才停机。
- **凭据管理**：API Key 经 Windows Credential Manager 存储（keyring），不落日志/配置/Git。
- **WebUI 演示**：FastAPI + Jinja2 + HTML/CSS/vanilla JS，3 个预设场景确定性执行，
  demo 模式仅用 Mock 外部边界（无真实 LLM/Shell/文件系统/网络/凭据）。

## 快速开始

要求：Windows + Python 3.12。

```bat
git clone <repo-url>
cd ai4sepa
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements\dev.txt
python -m codeguard --help
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `python -m codeguard chat [--mode test\|local\|demo]` | 交互式 Agent 会话 |
| `python -m codeguard demo [a\|b\|c]` | 运行预设演示场景 |
| `python -m codeguard web [--host H] [--port P]` | 启动 WebUI demo（默认 127.0.0.1:8080） |
| `python -m codeguard key set\|status\|update\|clear --provider deepseek` | 管理 API Key |
| `python -m codeguard config` | 显示生效配置 |

## WebUI 演示

```bat
python -m codeguard web
```

打开 http://127.0.0.1:8080 ，三个演示场景：

- **场景 A — 治理拦截**：LLM 提议越界写文件 → BLOCK → 反馈回灌 → 改为安全动作 → COMPLETED
- **场景 B — 审批流**：副作用动作 → REQUEST_APPROVAL → 批准 → COMPLETED / 拒绝或超时 → CANCELLED
- **场景 C — 失败修复**：写入 buggy 代码 → 传感器 FAILED → 分类回灌 → 修复 → 二次通过 → COMPLETED

demo 模式运行真实 Harness 核心，外部边界全部 Mock；页面顶部有 MOCK 横幅。
浏览器会话相互隔离（独立 session_id + 独立内存状态）。

## DeepSeek API 配置

1. 设置 Key（隐藏输入，存入 Windows Credential Manager）：
   ```bat
   python -m codeguard key set --provider deepseek
   ```
2. 查看/更新/清除：
   ```bat
   python -m codeguard key status --provider deepseek
   python -m codeguard key update --provider deepseek
   python -m codeguard key clear --provider deepseek
   ```
3. 连通性测试（**手动脚本，不在 CI**，需要真实 Key）：
   ```bat
   python -m codeguard key set --provider deepseek
   python scripts\deepseek_smoke_test.py
   ```
   smoke test 从 Credential Manager 读取 Key，不通过命令行参数或环境变量传递。**不要**使用
   `set DEEPSEEK_API_KEY=...`（会进入命令历史）。

测试套件使用 `ScriptedMockLLM`，不依赖真实 LLM、网络或 API Key。

## 分发（PyInstaller 打包）

在 Windows 上构建单文件 exe：

```bat
pip install pyinstaller
pyinstaller codeguard.spec
```

产物：`dist\codeguard.exe`（含 WebUI 模板与静态资源）。exe 支持全部 CLI 子命令。

SHA-256 校验：

```bat
certutil -hashfile dist\codeguard.exe SHA256
```

比对仓库记录/CI artifact 中 `dist\codeguard.exe.sha256` 的哈希值。

> **SmartScreen 警告**：exe 未签名，Windows SmartScreen 可能提示"未知发布者"。
> 点击"更多信息 → 仍要运行"，并用上方 SHA-256 校验完整性。

GitHub Actions `build-exe` job 在 `windows-latest` 上自动构建并上传
`codeguard.exe` 与 `codeguard.exe.sha256` artifact。

## CI

- `.gitlab-ci.yml` — GitLab CI：`python:3.12` 容器运行全量 pytest（仅 main 分支）。
- `.github/workflows/ci.yml` — GitHub Actions：ubuntu unit-test + windows build-exe。
- CI 不访问真实 LLM、外部业务 API 或真实凭据；不配置 API Key Secrets。

## 交付方式

**正式交付**：GitHub Release（`dist/codeguard.exe` + `dist/codeguard.exe.sha256`）。

WebUI 为本地功能：

```bat
codeguard.exe web
```

启动后打开 http://127.0.0.1:8080 即可访问 Mock-only WebUI 演示。

Render 部署为可选方案（`render.yaml` 已配置，当前未部署）。

## 架构概览

```
CLI (__main__.py)
 ├─ chat     → AgentLoop（状态机 INITIALIZING→…→COMPLETED/FAILED/…）
 ├─ demo     → CompositionRoot(mode="demo") + 脚本化 Mock 场景
 ├─ web      → FastAPI WebUI（demo 模式，Jinja2 模板 + vanilla JS）
 ├─ key      → KeyringCredentialStore（Windows Credential Manager）
 └─ config   → 4 层配置加载 + 按字段类型安全合并
```

核心包：`codeguard/loop`（Agent 主循环与状态机）、`codeguard/guardrail`
（规则引擎/审批/归一化）、`codeguard/feedback`（传感器与三层分类）、
`codeguard/memory`（跨会话记忆）、`codeguard/credentials`（凭据存储）、
`codeguard/config`（分层配置）、`codeguard/demo`（Mock 边界与演示场景）、
`codeguard/web`（WebUI）。

## 测试

```bat
pytest -v
```

622 个测试全部离线确定性运行：ScriptedMockLLM / MockToolDispatcher /
MockMemoryStore / MockCredentialStore / FakeClock，无真实 LLM、无网络、无 API Key。

详见 `SECURITY.md`（威胁模型、fail-closed 策略、SecretRedactor、SmartScreen 说明）。
