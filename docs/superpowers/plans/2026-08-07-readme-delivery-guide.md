# README Delivery Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将乱码的 `README.md` 重写为主要面向老师和助教、可直接照做的课程验收与运行指南。

**Architecture:** README 采用双入口结构：前半部分给老师/助教提供 EXE 快速验收和预期结果，后半部分给开发者提供源码复现、架构、安全、CI 与依赖信息。所有命令以当前 `codeguard.exe` 帮助和两份课程要求为准，不新增或虚构功能。

**Tech Stack:** Markdown、Windows Command Prompt、Python 3.12、PyInstaller、FastAPI、pytest。

## Global Constraints

- 只修改 `README.md`，不修改实现代码、构建产物、SPEC、PLAN 或其他课程文档。
- 主要读者是老师和助教，普通开发者复现为次要入口。
- WebUI 是由本地 EXE 启动的 Mock-only 演示，不描述为已部署的公网服务。
- `chat` 是一次性 Harness 会话，不描述为持续交互式聊天。
- API Key 仅通过隐藏输入写入 Windows Credential Manager，不在命令、日志或配置中展示明文。
- 已知限制中客观说明课程 API 额度约束及后续多轮聊天、流式回复计划。
- 不保留乱码、示例姓名、TODO/TBD 或不可执行占位符。

---

### Task 1: 重写并验证课程验收 README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `dist/codeguard.exe` 的 `--help`、`chat --help`、`demo --help`、`web --help`；两份课程要求；当前 Release 交付方案。
- Produces: 老师/助教可按顺序执行的验收指南，以及开发者可从源码复现的说明。

- [ ] **Step 1: 用正常 UTF-8 中文重写 README**

按以下顺序完整重写：

1. 项目简介与主要贡献。
2. “老师/助教：5 分钟快速验收”，包含 Release 下载、SHA-256、`--help`、`demo a/b/c`、`web` 和每项预期结果。
3. CLI 命令表及 `chat` 一次性会话说明。
4. API Key 的 set/status/update/clear 安全流程。
5. 从源码运行与测试。
6. A/B/C Mock 机制演示。
7. 安全边界、目录结构、架构概览。
8. 分发、CI、平台限制、第三方依赖。
9. 已知限制、后续工作和课程文档索引。

- [ ] **Step 2: 核对命令与课程要求**

Run:

```powershell
dist\codeguard.exe --help
dist\codeguard.exe chat --help
dist\codeguard.exe demo --help
dist\codeguard.exe web --help
```

Expected: README 中出现的参数和子命令均能在帮助输出中找到；不出现持续聊天或公网部署承诺。

- [ ] **Step 3: 扫描乱码、占位符和 Markdown 结构**

Run:

```powershell
rg -n "æ|ç|è|TODO|TBD|FIXME|<repo-url>|张三|xxx/yyy" README.md
rg -n "^#{1,4} " README.md
```

Expected: 第一条无匹配；第二条显示完整且层级合理的标题目录。

- [ ] **Step 4: 检查差异与空白错误**

Run:

```powershell
git diff --check -- README.md
git diff -- README.md
```

Expected: 无空白错误；差异只包含 README 重写。

- [ ] **Step 5: 提交 README**

```powershell
git add README.md
git commit -m "docs: rewrite README as teacher-facing delivery guide"
```
