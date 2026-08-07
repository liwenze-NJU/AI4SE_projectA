# README 交付指南重构设计

## 目标

将 `README.md` 重构为老师和普通使用者都能直接执行的交付指南，同时修复现有中文乱码。README 必须准确回答：项目解决什么问题、如何获取和启动、如何安全配置 API Key、如何运行机制演示、如何从源码复现，以及有哪些平台和安全限制。

## 读者与入口

README 面向两类读者：

1. **老师/助教**：优先使用 GitHub Release 中的 Windows 单文件 EXE，在数分钟内完成离线验收。
2. **开发者**：使用 Python 3.12 从源码安装依赖、运行 CLI、WebUI 和全量测试。

因此首页先给出“老师快速验收”，再提供源码运行、功能细节和架构说明。

## 内容结构

1. 项目简介、主要贡献和安全边界。
2. 老师快速验收：下载、SHA-256 校验、CLI 帮助、A/B/C 演示、WebUI 启动及预期结果。
3. CLI 使用：`chat`、`demo`、`web`、`key`、`config`，明确 `chat` 是一次性 Harness 会话。
4. API Key 安全配置：隐藏输入、Windows Credential Manager、状态/更新/清除流程。
5. 从源码运行：Python 3.12、虚拟环境、依赖安装和测试命令。
6. 三个 Mock 场景、核心机制、目录结构与架构。
7. 二进制分发、CI、平台限制、SmartScreen、可选 Render 配置。
8. 第三方依赖和课程交付文档索引。

## 准确性约束

- 只写当前代码和最新 EXE 已支持的行为，不承诺持续聊天、在线 WebUI 或尚未创建的 Release URL。
- WebUI 明确为 `codeguard.exe web` 启动的本地 Mock 演示，与真实 API Key 隔离。
- GitHub Release 链接在正式发布后使用仓库 Release 页面；README 不保留 `<repo-url>` 一类无法执行的占位符。
- 测试数量使用当前最新验证结果，并说明 Windows 符号链接测试可能跳过。
- 不修改实现、构建产物、SPEC、PLAN 或其他课程文档。

## 验证

- 扫描 README 是否残留乱码、TODO/TBD、示例姓名或占位链接。
- 对照 `codeguard.exe --help` 及各子命令帮助核对命令。
- 检查 Markdown 围栏、链接和标题结构。
- 使用 `git diff --check` 检查空白错误。
