# CodeGuard WebUI — UI Design Brief

> 本文档仅从已确认的 SPEC.md 和设计决策中提取，不增加实现范围。

---

## 1. 项目背景与目标用户

**CodeGuard Harness** 是一个面向 Windows 的本地 Coding Agent Harness，核心是 Agent = LLM + Harness 的实现。WebUI 是其附属组件。

**目标用户**：需要在本地受控环境中使用 AI 辅助编码的开发者，要求在危险操作执行前有人工审批、测试结果可客观反馈并驱动自我修正。WebUI 的观众还包括课程评审、评估者及对 harness 机制感兴趣的技术人员。

## 2. WebUI 定位

WebUI 是 Harness 的**安全、可重复的机制演示界面**，不是在线代码编辑器，也不是可执行真实编码任务的云端 Agent。

**设计约束**：
- 线上 WebUI 只允许用户选择预定义 Mock 场景并观察状态变化
- 不提供任意任务输入、任意 Shell 命令输入、真实文件上传或修改
- 不提供真实 Git 仓库访问、真实 LLM、真实 API Key
- 无外部网络访问
- 无从 demo 切换到 local 的功能

## 3. 安全边界（必须从 UI 层面体现）

| 禁止项 | 原因 |
|--------|------|
| 真实 Shell 执行 | DemoCompositionRoot 不导入 LocalToolExecutor |
| 宿主文件系统写入 | 使用模拟文件系统 |
| 真实 LLM 调用 | 固定使用 ScriptedMockLLM |
| 真实凭据读取 | 不导入 KeyringCredentialStore |
| 任意工具调用按钮 | 仅提供预设场景控制 |

UI 必须**明确展示"DEMO MODE"和安全状态**，包括：ScriptedMockLLM、MockToolDispatcher、MockMemoryStore、MockFileSystem、No real execution、No credentials loaded。

## 4. 必须展示的内容

### 4.1 Agent 状态机

展示步骤状态转换，当前状态突出显示，并允许查看每一步的时间和结果：

```
INITIALIZING → BUILDING_CONTEXT → DECIDING → GOVERNING
→ AWAITING_APPROVAL（必要时）
→ EXECUTING → INTERMEDIATE_VALIDATION → FEEDING_BACK
→ LLM 返回 COMPLETE_REQUEST → FINAL_VALIDATION → COMPLETED
```

终态：COMPLETED / FAILED / CANCELLED / LIMIT_REACHED → FINALIZING

### 4.2 执行轨迹（Trace Timeline）

按时间顺序展示：
- 状态转换
- LLM Action（工具名称、参数摘要）
- Guardrail 决策
- Mock ToolResult
- FeedbackResult
- 下一轮 Action
- StopPolicy 结果

### 4.3 治理决策（ALLOW / BLOCK / REQUEST_APPROVAL）

展示经过脱敏的：
- 工具名称
- 规范化参数
- Guardrail decision（ALLOW / BLOCK / REQUEST_APPROVAL）
- risk level
- matched rule IDs
- reason
- 审批结果

### 4.4 审批流程

展示：
- 当前 pending request 详情
- 批准按钮（绑定具体 Action）
- 拒绝按钮
- 超时状态
- 审批结果反馈

### 4.5 反馈闭环

展示：
- sensor name
- 三层分类（执行状态 → 失败类别 → 诊断详情）
- failure fingerprint
- MockLLM 下一轮 Action 是否发生变化

### 4.6 Memory 摘要

当前会话记忆记录的简要摘要（来源、信任等级、状态）。

## 5. 三个确定性 Mock 演示场景

| 场景 | 展示内容 | 核心验证点 |
|------|---------|-----------|
| 危险动作 BLOCK | Guardrail 拦截路径逃逸/BLOCK → LLM 收到反馈后改变 Action | 默认拒绝策略 |
| REQUEST_APPROVAL 审批 | Guardrail 触发审批 → AWAITING_APPROVAL → 用户批准/拒绝/超时 | 审批绑定具体 Action |
| 反馈闭环 | 第一次失败 → FeedbackClassifier 分类 → 回灌 → LLM 改变 Action → 最终通过 | 三层分类 + 自我修正 |

## 6. Vercel Design System 使用边界

**借鉴范围**：
- 排版：Geist 字体风格（Geist Sans 标题 + Geist Mono 代码/技术标签）
- 颜色：黑白主色（#ffffff 背景 / #171717 文字）+ 工作流强调色
- 按钮：简洁、清晰的状态按钮
- 卡片：信息展示卡片
- 状态标签：pill badges 风格
- 对话框：审批对话框布局
- 间距：Vercel 的宽松间距系统

**不借鉴**：
- Vercel Logo、商标或具体业务页面
- 不复制 Vercel 的导航、页脚、部署流程等业务元素

## 7. 可访问性与投影要求

- **高对比度**：文字与背景对比度符合 WCAG AA 标准
- **不依赖颜色**：状态（ALLOW/BLOCK/APPROVAL）不能只靠颜色区分，必须配合文字标签或图标
- **教室投影**：字号足够大（至少 16px 正文），状态标签清晰可读
- 支持基本键盘导航（Tab 切换、Enter 确认）

## 8. 技术约束

| 项目 | 约束 |
|------|------|
| 后端框架 | FastAPI（Python） |
| 模板引擎 | Jinja2 |
| 样式 | CSS（手写，基于 Vercel 规范） |
| 交互 | 原生 JavaScript |
| 实时更新 | REST + 简单轮询（不引入 WebSocket） |
| 前端构建 | 无（不引入 React、Node.js、npm、webpack） |
| 部署 | Render 固定 Demo Mode |
| 本地地址 | 默认绑定 127.0.0.1 |

## 9. 当前阶段禁止输出

- 禁止编写 HTML/CSS/JS 实现代码
- 禁止创建 FastAPI 路由
- 禁止生成 Jinja2 模板
- 禁止修改 CI、打包或部署配置
- 禁止 commit 或 push

## 10. 本轮交付物

Open Design 本轮需要交付：
| 交付物 | 格式 | 说明 |
|--------|------|------|
| PROJECT_DESIGN.md | Open Design 产出 | 项目专属设计规范 |
| WIREFRAME_SPEC.md | 文档 | 页面布局和线框图说明 |
| 线框图 | 图片/截图 | 低保真或高保真页面布局 |
| 设计评审记录 | 文档 | 人工评审和迭代记录 |