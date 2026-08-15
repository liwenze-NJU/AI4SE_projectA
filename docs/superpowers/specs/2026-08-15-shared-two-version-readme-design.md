# 双版本共用 README 设计

## 目标

为 `main` 与 `feature/interactive-cli-agent` 提供内容完全相同的 `README.md`。README 采用中立叙事，在开头明确仓库包含两个彼此独立的版本，帮助老师、助教和开发者选择正确的分支、Release、运行方式与验收流程。此次工作只更新文档，不把增强版代码合并进 `main`。

## 版本定位

README 将两个版本并列展示，不使用“当前版本”“主版本”等依赖所在分支的表述：

| 版本 | 分支 | 版本号 | 定位 |
| --- | --- | --- | --- |
| 课程版 | `main` | `0.1.1` | 已提交的课程验收基线，提供一次性 Harness 会话、Guardrail、反馈闭环、离线演示与 Mock WebUI |
| 交互式增强版 | `feature/interactive-cli-agent` | `0.2.0-interactive` | 在独立分支上增加持续聊天 REPL、真实 DeepSeek 适配、受治理工具、会话上下文和更完整的 CLI 交互 |

README 必须明确：增强版没有合并回 `main`；两个分支保存两个可分别获取、构建和测试的代码版本。

## 内容结构

1. 项目简介与双版本说明。
2. 版本选择表、分支链接、Release 链接和 Git 获取命令。
3. 课程版功能介绍与快速验收流程。
4. 交互式增强版功能介绍与完整人工验收流程。
5. 两个版本共用的 Harness 状态机、核心模块和安全边界。
6. 从源码安装、运行测试和构建 Windows EXE 的说明。
7. CLI、离线 Demo、Mock WebUI、API Key 和 SHA-256 使用说明。
8. 目录结构、CI/发布、第三方依赖、已知限制和课程文档索引。
9. 课程提交说明。

## 课程版章节

课程版章节保留现有 README 的主要内容：

- 显式 Agent 状态机、Guardrail、审批和测试反馈闭环；
- `chat` 为一次性 Harness 会话；
- `demo a`、`demo b`、`demo c` 为确定性离线 Mock 场景；
- `web` 提供本地 Mock WebUI；
- `key` 与 `config` 命令、安全边界和源码复现方法；
- 对应 `main` 分支和 `0.1.1` 版本，不把增强功能描述为课程版已有功能。

## 增强版章节

增强版章节保留已经实现和人工验证的功能：

- `codeguard chat --mode local` 持续多轮 REPL；
- DeepSeek 凭据通过系统 Keyring 保存；
- 工作区内文件读取、搜索、多文件补丁、测试和结构化进程执行；
- Guardrail 对写入和进程工具进行审批，对越界路径、未知工具和凭据访问 fail-closed；
- 任务间摘要、澄清提问、取消、终态验证和工具结果反馈；
- 工具输出和模型上下文中的敏感字段脱敏；
- `CODEGUARD_PYTHON` 用于为冻结 EXE 指定带 pytest 的外部 Python 环境；
- 当前限制包括无流式 Token、无 CLI 模型切换、无多 Agent 并行、WebUI 仍为 Mock 演示。

## 验收设计

README 将验收拆成两条明确路径：

### 课程版快速验收

- 检查版本、帮助和配置；
- 执行三个离线 Demo；
- 启动 WebUI 并检查 `/health`；
- 需要时从源码运行课程版测试。

### 增强版人工验收

- 下载 `codeguard.exe` 与 `codeguard.exe.sha256` 并核对 SHA-256；
- 检查 `0.2.0-interactive`、帮助、配置和 REPL 内置命令；
- 验证跨任务会话上下文只显示一次最终回复；
- 验证 BOM 文件的多文件 `apply_patch`、逐次审批、pytest 和最终终态；
- 验证拒绝审批不会修改文件；
- 验证工作区逃逸被拦截；
- 验证敏感值在工具输出中被替换为 `***`；
- 验证结构化 `run_process` 的 `program` 与 `args`；
- 验证离线 Demo、Mock WebUI 和 `/health`。

验收命令以 PowerShell 为主，并说明必须在选定版本对应的源码目录或 Release EXE 所在目录运行。

## 发布与链接

- 仓库地址统一使用 `https://github.com/liwenze-NJU/AI4SE_projectA`。
- 课程版链接指向 `main` 和已有课程版标签/Release；如果没有独立 Release，则明确课程版可从 `main` 获取，避免虚构下载地址。
- 增强版使用分支 `feature/interactive-cli-agent`，正式 Release 标签为 `v0.2.0-interactive`。
- README 可以提前使用确定的增强版 Release 地址 `https://github.com/liwenze-NJU/AI4SE_projectA/releases/tag/v0.2.0-interactive`，该地址在 Release 发布后生效。
- Release 创建前，必须先让最终 README 进入增强分支提交并通过 CI，使 tag 对应的源码快照包含最终 README。

## 一致性与范围约束

- 两个分支的 `README.md` 必须逐字节一致。
- README 不根据当前分支动态改变措辞。
- `main` 只接收同一份 README，不接收增强实现、测试、构建或配置变更。
- 不修改两个版本的 `SPEC.md`、`PLAN.md`、`AGENT_LOG.md`、`REFLECTION.md` 或实现代码。
- 删除过时测试数量和与当前实现冲突的限制描述；测试数量优先引用相应日志或写成不易过时的“以最新 CI 为准”。
- 不暴露真实 API Key、用户名、绝对本机路径或人工验收中的私密内容。

## 验证标准

1. 使用二进制比较确认两个 `README.md` 完全一致。
2. 检查两个工作树的 Git diff，确保除设计/计划记录外，交付修改只涉及 README。
3. 扫描 README 中的 `TODO`、`TBD`、占位链接、真实凭据和本机绝对路径。
4. 核对分支名、版本号、CLI 命令、Release 地址和 PowerShell 示例。
5. 检查 Markdown 标题、表格、代码围栏和相对链接。
6. 对两个工作树执行 `git diff --check`。
7. 分别提交并推送文档修改，确认增强分支最新 CI 通过后再创建正式 Release。
