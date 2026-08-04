# CodeGuard WebUI — Open Design 设计证据

本目录用于保存 CodeGuard Harness WebUI 的 Open Design 设计过程证据。

## 声明

- Open Design 是**开发阶段设计工具**，不是 CodeGuard 的运行依赖
- 最终 WebUI 使用 FastAPI + Jinja2 + HTML/CSS + 原生 JavaScript 实现
- 不引入 React、Node.js 构建流程或 Open Design 运行时依赖

## 当前阶段约束

在 SPEC 最终确认、PLAN 生成和冷启动验证完成之前，本目录**只允许**包含：
- 设计文档（DESIGN.md、UI_DESIGN_BRIEF.md、INFORMATION_ARCHITECTURE.md 等）
- 线框图（wireframes/）
- 静态图片（screenshots/）
- 评审记录（reviews/）

**禁止**在本目录中生成正式 HTML/CSS/JS/Python 实现代码。

## 后续预期产物

| 文件/目录 | 作用 |
|-----------|------|
| UI_DESIGN_BRIEF.md | 输入给 Open Design 的设计约束 |
| DESIGN.md | 项目专属视觉规范（基于 Vercel Design System） |
| INFORMATION_ARCHITECTURE.md | 页面和信息层级 |
| WIREFRAME_SPEC.md | 线框图说明 |
| wireframes/ | 低保真线框图 |
| screenshots/ | Open Design 操作及结果证据 |
| reviews/ | 人工评审和设计迭代记录 |