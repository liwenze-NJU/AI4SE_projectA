# 第一轮人工决策记录 — ROUND_01_HUMAN_DECISIONS.md

> 对应评审：`ROUND_01_REVIEW.md §4` C1–C8
> 本文档记录已确认的 C1–C8 全部决策，作为 SPEC 最终确认的前置条件。

---

## C1：SPEC 阶段文档化模式

**决策**：认可 Web Prototype 文档化模式，不生成实现代码。

**补充说明**：Open Design 的 `Web Prototype` skill 以文档化模式运行，仅产出设计文档（`.md`）和 ASCII 线框图，不生成 HTML/CSS/JS 实现代码。

**确认时间**：2026-08-03

**影响范围**：全局交付形态 — 9 个设计文档均为 `.md` 格式，无实现代码。

---

## C2：未来实现轮技术栈

**决策**：正式技术栈固定为 FastAPI + Jinja2 + HTML/CSS + 原生 JavaScript，不引入 React、Node.js 或前端构建流程。

**补充说明**：不预留"轻量框架"选项。前端构建流程（npm/webpack/vite 等）全部排除。CSS 手写，基于 Vercel 视觉规范。

**确认时间**：2026-08-03

**影响范围**：`DESIGN.md §9`、`SPEC.md §3.9`、`SPEC.md §9` 技术选型表

---

## C3：场景 A 终态

**决策**：场景 A 中危险动作先被 BLOCK 且绝不执行；反馈回灌后 Agent 改用安全动作，验证通过后最终状态为 COMPLETED。

**补充说明**：这不是"两可"或"依脚本预设"。Guardrail BLOCK 后进入 FEEDING_BACK，Agent 收到反馈后改变 Action，新 Action 通过 GOVERNING，最终验证通过进入 COMPLETED。

**确认时间**：2026-08-03

**影响范围**：P2 步进器 / P4 药丸 / 线框图 / `SPEC.md §3.1` 状态机

---

## C4：场景 B 超时行为

**决策**：审批超时产生 TIMEOUT，Session 进入 CANCELLED，待审批动作绝不执行。

**补充说明**：超时不是"依脚本预设"，不是"继续执行"，不是"视为批准"。TIMEOUT 与 REJECTED 有相同效果：动作不执行，Session 终止。

**确认时间**：2026-08-03

**影响范围**：`SPEC.md §3.4` 审批流程、状态转换矩阵

---

## C5：P3 审批模态倒计时时长

**决策**：

| 场景 | 超时时间 |
|------|---------|
| WebUI Mock 普通审批默认 | 15 秒 |
| Mock 超时场景预设 | 5 秒 |
| WebUI Mock 可配置范围 | 5–60 秒 |
| 本地 CLI 审批默认 | 300 秒（见 SPEC.md §3.4） |

**补充说明**：
- 第一版不提供暂停倒计时功能。
- 测试使用 FakeClock/可注入时钟，不真实等待。
- 删除所有"课堂演示"理由（本项目不存在课堂现场讲解，最多录制演示视频）。

**确认时间**：2026-08-03

**影响范围**：P3 模态 / `SPEC.md §3.9` WebUI 章节 / `WIREFRAME_SPEC.md` / `wireframes/03-approval-dialog.md`

---

## C6：Memory 摘要条目类型枚举

**决策**：以 SPEC.md 的 `MemoryRecord` 数据模型为唯一规范来源，确认四种正式 `MemoryType`：

| 英文枚举 | 中文展示名称 | 说明 |
|---------|-------------|------|
| `PROJECT_CONVENTION` | 项目约定 | 跨会话项目约定 |
| `APPROVED_DECISION` | 已批准决策 | 用户批准的决策记录 |
| `TASK_SUMMARY` | 任务摘要 | 会话任务摘要 |
| `FAILURE_RESOLUTION` | 失败解决方案 | 验证后的失败解决经验 |

**修正处理**（Open Design 原五类 → 正式四类）：

| 原五类（Open Design） | 处理方式 | 映射到 |
|---------------------|---------|--------|
| 已审批动作 | 不作为独立类型，修正为"已批准决策" | `APPROVED_DECISION` |
| 测试失败 | 不作为跨会话 MemoryType；属于当前 Session 的 Feedback/Trace；只有经过验证且值得跨会话保留的解决经验才写入 | `FAILURE_RESOLUTION`（仅限已验证的解决经验） |
| 修复策略 | 修正为"失败解决方案" | `FAILURE_RESOLUTION` |
| 测试结果 | 不作为独立 MemoryType；可作为 `TASK_SUMMARY` 的内容，使用 `verified-test-result` 等标签表达 | `TASK_SUMMARY` + tags |
| 用户偏好 | 不作为独立 MemoryType；在确实属于项目约定时保存 | `PROJECT_CONVENTION` + `user-preference` 标签 |

**补充边界规则**（已记录到 SPEC.md）：

1. Memory 类型必须使用代码枚举验证，未知类型写入时拒绝，不能静默映射。
2. UI 中文名称只是展示标签，持久化和接口中仍使用正式英文枚举值。
3. tags 只能辅助检索，不能替代 MemoryType。
4. 原始测试失败、完整测试输出、原始工具输出和完整聊天不得自动写入跨会话记忆。
5. LLM 仅能通过 `memory_propose_write` 创建 PENDING 候选，不能直接创建 ACTIVE 记忆。
6. PENDING、REJECTED、ARCHIVED、DELETED 不得自动注入上下文。
7. 只有符合 SPEC 信任等级和状态要求的记录才能被检索注入。
8. WebUI Demo 使用 MockMemoryStore，但必须展示与真实 MemoryRecord 相同的四种类型和字段语义。
9. 单元测试至少覆盖：四个合法 MemoryType、未知类型被拒绝、中文展示标签到英文枚举的确定性映射、测试失败不会被直接固化为跨会话记忆、经过验证的失败解决方案可以进入 FAILURE_RESOLUTION、tags 不改变 MemoryType、不符合状态/信任要求的记录不自动注入。

**确认时间**：2026-08-03

**影响范围**：`SPEC.md §3.7` / `DESIGN.md` / `WIREFRAME_SPEC.md` / `wireframes/04-session-results.md`

---

## C7：磁盘 UI_DESIGN_BRIEF.md

**决策**：磁盘中已存在 `docs/design/open-design/UI_DESIGN_BRIEF.md`，须以它为准重新进行覆盖性检查，确认 ROUND_01_REVIEW.md 的符合性判定在磁盘版本下仍然成立。

**当前状态**：覆盖性检查已完成（见本轮验证项 3），磁盘版本与请求内嵌简报无实质性差异，ROUND_01_REVIEW.md §5 的符合性判定在磁盘版本下仍然成立。

**确认时间**：2026-08-03

**影响范围**：`ROUND_01_REVIEW.md §1` 判定基准

---

## C8：窄屏设计详细程度

**决策**：桌面优先，窄屏仅做最低限度自适应，不进行完整移动端专项设计。

**确认时间**：2026-08-04

**边界规则**：
1. 主要设计与验收视口为桌面端，目标宽度 1366×768 及以上。
2. 不创建独立移动端页面、移动导航或专门的移动端交互流程。
3. 窄屏 <768px 时只保证基本可读、可滚动和可操作：
   - 多栏仪表盘按顺序堆叠为单栏；
   - Agent 状态步进器保持横向滚动，不额外重构为另一套状态组件；
   - 表格和较宽 Trace 内容允许在组件内部横向滚动；
   - 审批模态宽度限制在视口内，按钮可纵向排列；
   - 不得出现页面级不可控横向溢出；
   - Mock Demo Mode 横幅仍保持可见；
   - 关键按钮触达区域保持至少 44×44px。
4. 窄屏只保证功能不损坏，不承诺与桌面端相同的信息密度和视觉效果。
5. 不做完整手机端视觉稿、移动端动画、手势或触屏专项优化。
6. 自动化验收至少检查一个 375px 宽窄屏视口：
   - 页面可打开；
   - 关键文字可读；
   - 场景可以选择；
   - 审批可以批准或拒绝；
   - 显式滚动区域可用；
   - 不存在遮挡关键按钮的布局错误。

**影响范围**：`WIREFRAME_SPEC.md` / 线框图 / `SPEC.md §3.9` WebUI 边界条件