# 第一轮设计评审 — ROUND_01_REVIEW.md

> 项目：CodeGuard Harness · WebUI 规约阶段
> 轮次：第 1 版（第一版设计，待人工评审）
> 评审对象：本轮产出的设计资料（见 §7 清单）
> 评审依据：用户请求中给出的简报条款（"一、项目背景"至"八、结束条件"），等价于 `UI_DESIGN_BRIEF.md` 全文。

---

## 1. 简报来源与磁盘文件状态说明

- 用户指示"开始前请阅读当前工作目录中的 `README.md` 与 `UI_DESIGN_BRIEF.md`"。
- 实测：当前工作目录（`…/projects/01525d5a-…/`）下**仅存在 `.od-skills/` 脚手架目录**，`README.md` 与 `UI_DESIGN_BRIEF.md` **均不存在于磁盘**（已通过 `Read` 与 `Glob` 确认）。
- 处理：用户请求消息本身已包含等价于 `UI_DESIGN_BRIEF.md` 的完整条款（"一"至"八"），故本评审的"逐项符合性检查（§6）"以**请求中给出的简报条款**为依据，而非磁盘文件。后续若用户提供磁盘 `UI_DESIGN_BRIEF.md`，应以其覆盖本评审中冲突的判定。

---

## 2. 第一版设计的主要决定

1. **单技能、文档化模式**：实际使用 Open Design skill `Web Prototype`，但因 SPEC 阶段禁令（禁产出 HTML/CSS/JS），本轮以**文档化模式**运行——采用其方法论（先吃透设计系统、先选布局再填文案、终末自检），成果落到 Markdown 设计文档与 ASCII 线框图，不产出任何 HTML/CSS/JS。预读步骤以系统提示中已注入的 `Vercel` `DESIGN.md`+`tokens.css` 替代 HTML seed，等价满足"先吃透系统"意图。
2. **设计系统 = Vercel**：严格绑定其 `tokens.css` `:root` 令牌；令牌块外不引入裸 hex；色彩派生一律用 `color-mix(in oklab, …)`。
3. **状态语义重映射**：把 Vercel 的"workflow 红/粉/蓝仅用于管线阶段"原则保留，但把 CodeGuard 的护栏/状态语义映射到 `--success/--warn/--danger/--accent`，**不复用** Vercel 的 Ship/Preview/Deploy 业务色名，避免与部署产品界面混淆。
4. **三重冗余铁律**：所有状态药丸 = 颜色 + 图标 + 中文文字，单独抽离色彩仍可完整理解（满足"状态不能只通过颜色表达"）。
5. **状态语义色豁免装饰预算**：Vercel"单屏 ≤2 强调色"的装饰预算保留，但**状态语义色（成功/警告/危险）明确豁免**，因其编码状态属功能色（Vercel 自身"色彩为功能"原则）；否则仪表盘多状态无法表达。
6. **投影地板调整**：正文 ≥18px、说明 ≥14px（Vercel 默认 16/12px）；仪表盘最大宽 1440px（Vercel 1200px）；display 负字距适度放宽至 -0.03em～-0.05em，兼顾品牌压缩感与远读可读性。
7. **Mock 安全表达三层**：常驻不可关闭顶部横幅（琥珀浅底+护盾+未连接项清单）+ 场景卡角标 + 数据级 `MOCK` mono 角标 + 底栏声明，四屏一致。
8. **P3 作模态层**：审批交互设计为仪表盘之上的模态对话框（非独立路由），回放到 `AWAITING_APPROVAL` 自动弹出并暂停回放；审批结束回灌轨迹后关闭，或拒绝直接进 P4。
9. **演示控件语义**：`步进/暂停/重放` 仅控制 Mock 脚本回放，文案明确为"演示步进"而非"执行命令"；不出现真实 Shell 输入框与 API Key 输入框。
10. **不预定实现技术栈**：`DESIGN.md §9` 仅记录未来实现轮的约束（自包含前端、不连真实环境、绑定 Vercel 令牌、AA 可访问、无复杂动画），具体 HTML+CSS+vanilla JS 或轻量框架**留待用户评审确认**，本轮不预定。

---

## 3. 尚未解决的问题

1. **`README.md` / `UI_DESIGN_BRIEF.md` 缺失**：磁盘无此二文件，本轮依据请求内嵌简报推进；若磁盘版本与请求内嵌条款有出入，需以磁盘版本覆盖。
2. **状态机终态分支语义**：场景 A 危险动作被 BLOCK 后，状态机转入 `FAILED` 还是 `CANCELLED`？本轮线框图在两处出现"FAILED/CANCELLED"并列，需评审确认脚本预设（影响 P4 终态药丸与 Memory 摘要措辞）。
3. **场景 B 超时行为**：超时后是继续回放（等同批准）还是转 `CANCELLED`？`WIREFRAME_SPEC §3.5` 暂记"依脚本"，需确认。
4. **倒计时时长**：P3 超时倒计时默认值本轮取演示用 30s（线框图示 23s 剩余为示例），需确认课堂演示合适时长。
5. **Memory 摘要条目类型枚举**：本轮预设 `[已审批动作]/[测试失败]/[修复策略]/[测试结果]/[用户偏好]` 五类药丸，需确认是否覆盖 CodeGuard 真实 Memory 结构。
6. **场景 A 是否触发测试反馈闭环**：本轮将场景 A/B 的反馈闭环卡设为简化版，需确认是否仍需在 P4 展示"未触发闭环"占位还是直接省略。
7. **窄屏步进器策略**：窄屏下水平步进器是横向滚动还是折叠为纵向时间线？本轮线框图标"横向可滚动"，需确认（简报以桌面优先，窄屏为次要）。
8. **Geist 字体可用性**：课堂投影机若未安装 Geist，回退到系统字体；需确认是否需要在实现轮内联 Geist 字体文件（涉及离线打包，属实现期决策）。

---

## 4. 需要用户人工确认的事项

| # | 确认项 | 本轮暂定 | 影响范围 |
|---|---|---|---|
| C1 | SPEC 阶段是否允许本轮产出的"文档化模式"（不产出 HTML）？ | 是（依禁令推断） | 全局交付形态 |
| C2 | 未来实现轮技术栈：HTML+CSS+vanilla JS / 轻量框架（如 React）/ 其他？ | 未预定 | `DESIGN.md §9` |
| C3 | 场景 A 终态：`FAILED` 还是 `CANCELLED`？ | 两可（线框并列） | P2 步进器 / P4 药丸 |
| C4 | 场景 B 超时行为：继续 / 转 `CANCELLED`？ | 依脚本（待定） | `WIREFRAME_SPEC §3.5` |
| C5 | P3 倒计时时长 | 30s（演示用） | P3 模态 |
| C6 | Memory 摘要条目类型枚举是否准确 | 五类（预设） | P4 / `DESIGN.md` |
| C7 | 是否需要提供磁盘 `UI_DESIGN_BRIEF.md` 以覆盖本评审判定 | —— | §1 / §6 判定基准 |
| C8 | 是否需要在窄屏（<768）详细设计，还是仅桌面优先即可 | 桌面优先，窄屏简略 | `WIREFRAME_SPEC` / 线框 |

> 建议用户就 C1–C8 逐项回复；其中 C1、C3、C4、C7 影响较大。

---

## 5. 与 UI_DESIGN_BRIEF 的逐项符合性检查

> 判定基准：用户请求内嵌简报条款（等价 `UI_DESIGN_BRIEF.md`）。磁盘文件缺失见 §1。
> 判定符号：✅ 符合 / ⚠️ 部分符合（见说明）/ ⏳ 待确认。

### 5.1 项目背景与设计目标（简报 一、二）

| 简报条款 | 判定 | 证据 |
|---|---|---|
| 面向 Windows 本地 CLI Coding Agent Harness 的在线 WebUI（安全 Mock Demo） | ✅ | `DESIGN.md §0/§1`、`IA §1` |
| 目标用户：教师/助教/开发者 | ✅ | `DESIGN.md §1` |
| 理解 Agent=LLM+Harness、LLM 决策、Harness 治理/执行/反馈/停机 | ✅ | `DESIGN.md §1`、`IA §3-P1`、`wireframes/01` |
| 危险动作 BLOCK 或请求审批 | ✅ | `DESIGN.md §3.2`、`IA §6-A/B`、`wireframes/02/03` |
| 测试失败→结构化反馈→驱动修正 | ✅ | `DESIGN.md §6.8`、`IA §6-C`、`wireframes/02/04` |
| 安全可重复 Mock 场景 | ✅ | `DESIGN.md §8`、`IA §2/§6` |

### 5.2 设计系统（简报 三）

| 简报条款 | 判定 | 证据 |
|---|---|---|
| 使用 Vercel DS 的信息层级/排版/间距/卡片/按钮/状态标签/时间线/对话框规范 | ✅ | `DESIGN.md §2/§4/§5/§6` |
| 不复制 Vercel Logo/商标/具体业务页面/无关部署界面 | ✅ | `DESIGN.md §1/§6.9/§8`、`wireframes/00`（字标为 CodeGuard） |
| 写明实际使用的 Open Design skill 准确名称 | ✅ | `DESIGN.md §2.1/§10`：`Web Prototype`（文档化模式） |
| 写明 Vercel Design System 的准确名称 | ✅ | `DESIGN.md §2.1/§10`：`Vercel`（`design-systems/vercel`） |
| 写明哪些规范被采用 | ✅ | `DESIGN.md §2.2`（逐条采用表） |
| 写明哪些规范因课堂投影/可访问性而调整 | ✅ | `DESIGN.md §2.3`（逐条调整表） |

### 5.3 必须覆盖的页面与信息（简报 四）

| 简报条款 | 判定 | 证据 |
|---|---|---|
| 演示场景选择 | ✅ | `IA §3-P1`、`WIREFRAME_SPEC §1`、`wireframes/01` |
| Agent 运行仪表盘 | ✅ | `IA §3-P2`、`WIREFRAME_SPEC §2`、`wireframes/02` |
| 审批交互 | ✅ | `IA §3-P3`、`WIREFRAME_SPEC §3`、`wireframes/03` |
| 会话结果和 Memory 摘要 | ✅ | `IA §3-P4`、`WIREFRAME_SPEC §4`、`wireframes/04` |
| 醒目的 Mock Demo Mode 标识 | ✅ | `DESIGN.md §3.3/§8`、`wireframes/00`（常驻不可关闭横幅） |
| Agent 状态机 9 运行态 + 4 终态 | ✅ | `DESIGN.md §3.2`（全 13 态映射）、`wireframes/02`（步进器+时间线） |
| 执行轨迹 | ✅ | `DESIGN.md §6.7`、`wireframes/02`（中栏） |
| 工具调用 | ✅ | `DESIGN.md §6.7`、`wireframes/02`（右栏+轨迹展开行） |
| Guardrail 决策 ALLOW/BLOCK/REQUEST_APPROVAL | ✅ | `DESIGN.md §3.2`、`wireframes/02`（护栏三联卡） |
| 审批目标动作 | ✅ | `WIREFRAME_SPEC §3`、`wireframes/03`（标题 mono） |
| 风险原因 | ✅ | `DESIGN.md §6.6`、`wireframes/02/03` |
| 影响范围 | ✅ | `WIREFRAME_SPEC §3`、`wireframes/02/03` |
| 批准、拒绝、超时 | ✅ | `WIREFRAME_SPEC §3.3/§3.5/§3.6`、`wireframes/03`（三按钮+结果反馈） |
| 测试第一次失败 | ✅ | `wireframes/02`（失败行）、`wireframes/04`（闭环卡①） |
| 失败类别和诊断详情 | ✅ | `DESIGN.md §6.7`、`wireframes/02`（类别药丸+诊断折叠） |
| 反馈回灌 | ✅ | `DESIGN.md §3.2 FEEDING_BACK`、`wireframes/02/04` |
| Agent 下一步动作发生改变 | ✅ | `wireframes/04`（闭环卡③ 改动作） |
| 第二次测试通过 | ✅ | `wireframes/04`（闭环卡末段绿） |
| Memory 摘要 | ✅ | `DESIGN.md §6（隐含）`、`wireframes/04`（Memory 面板） |

### 5.4 三个确定性 Mock 场景（简报 五）

| 简报条款 | 判定 | 证据 |
|---|---|---|
| 场景 A：路径逃逸/危险动作被 BLOCK | ✅ | `IA §6-A`、`WIREFRAME_SPEC §6`、`wireframes/01/02` |
| 场景 B：有副作用但可能合法 → REQUEST_APPROVAL | ✅ | `IA §6-B`、`WIREFRAME_SPEC §6`、`wireframes/03` |
| 场景 C：第一次失败→反馈分类→改动作→第二次通过 | ✅ | `IA §6-C`、`wireframes/02/04` |

### 5.5 可访问性和演示要求（简报 六）

| 简报条款 | 判定 | 证据 |
|---|---|---|
| 桌面优先 | ✅ | `DESIGN.md §7`、`wireframes`（均桌面布局） |
| 1366×768 及以上 | ✅ | `DESIGN.md §7/§9` |
| 适合教室投影 | ✅ | `DESIGN.md §2.3/§4/§7`（投影地板字号） |
| 高对比度 | ✅ | `DESIGN.md §3.1/§7`（#171717/#fff ≈16:1） |
| 状态不只用颜色（文字/图标） | ✅ | `DESIGN.md §3.2/§7`（三重冗余铁律） |
| 不使用复杂动画 | ✅ | `DESIGN.md §2.3/§7`（仅 ≤200ms + reduced-motion） |
| 不设计可自由输入执行的真实 Shell | ✅ | `DESIGN.md §6.10/§8`（无 Shell 输入框） |
| 不出现真实 API Key 输入框 | ✅ | `DESIGN.md §6.10/§8`（无 API Key 字段） |
| 必须持续显示安全 Mock 模式 | ✅ | `DESIGN.md §3.3/§8`、`wireframes/00`（常驻横幅） |
| 界面重点是机制展示，不是聊天窗口 | ✅ | `IA §3`（无聊天 UI；仪表盘/轨迹/审批/结果） |

### 5.6 本轮交付物（简报 七）

| 简报条款 | 判定 | 证据 |
|---|---|---|
| `DESIGN.md` 含设计目标/采用方式/色彩状态语义/字体层级/间距/组件/可访问性/Mock安全/实现技术约束/skill名 | ✅ | `DESIGN.md §1–§10`（十项俱全） |
| `INFORMATION_ARCHITECTURE.md` 含页面列表/每页职责/页面间导航/信息优先级/用户操作流程 | ✅ | `IA §2/§3/§4/§5/§6`（五项俱全） |
| `WIREFRAME_SPEC.md` 含每页布局/各区域作用/组件状态/空状态/错误状态/审批状态/完成状态 | ✅ | `WIREFRAME_SPEC §1–§5`（七项俱全，逐页覆盖） |
| `reviews/ROUND_01_REVIEW.md` 含主要决定/未解决问题/需确认事项/逐项符合性检查 | ✅ | 本文件 §2/§3/§4/§5 |
| `wireframes/` 下低保真线框图或静态设计图 | ✅ | `wireframes/00–04`（5 个 ASCII 线框图） |

### 5.7 结束条件（简报 八）

| 简报条款 | 判定 | 证据 |
|---|---|---|
| 列出实际生成的文件 | ✅ | 本文件 §7 |
| 显示实际使用的 Open Design skill 准确名称 | ✅ | 本文件 §7/§2-决定1；`DESIGN.md §10` |
| 总结关键设计决策 | ✅ | 本文件 §2 |
| 明确说明没有生成任何正式实现代码 | ✅ | 本文件 §8 |
| 等待用户人工评审 | ✅ | 本文件 §9（本轮到此为止，不自行迭代） |

### 5.8 严格禁止生成/修改清单（简报"严格禁止"段）

| 禁止项 | 判定 | 证据 |
|---|---|---|
| Python / FastAPI / Jinja2 | ✅ 未生成 | 交付物均为 `.md` |
| HTML / CSS / JavaScript / React | ✅ 未生成 | 同上（含 skill 以文档化模式运行，不产出 HTML） |
| Node.js 项目 | ✅ 未生成 | 同上 |
| 测试代码 / CI/CD / 打包部署配置 | ✅ 未生成 | 同上 |
| CodeGuard 正式源代码 | ✅ 未生成 | 同上 |

---

## 6. 符合性总评

- **符合**：简报"二–八"全部要求与"严格禁止"清单均已覆盖或遵守；未发现缺失项。
- **部分符合/待确认**：§3 中 8 项未决问题与 §4 中 C1–C8 待确认事项，均不影响"第一版设计完整性"，但需用户评审后定稿。
- **风险**：磁盘 `README.md`/`UI_DESIGN_BRIEF.md` 缺失（§1），本评审以请求内嵌简报为依据；若磁盘版本存在差异，需以磁盘版本覆盖。

---

## 7. 本轮交付物清单

| 文件 | 说明 |
|---|---|
| `DESIGN.md` | 设计规格（目标/Vercel 采用/色彩状态语义/字体/间距/组件/可访问性/Mock/实现约束/skill 名） |
| `INFORMATION_ARCHITECTURE.md` | 信息架构（页面列表/职责/导航/优先级/操作流程） |
| `WIREFRAME_SPEC.md` | 线框图规格（每页布局/区域/组件状态/空/错误/审批/完成状态） |
| `wireframes/00-app-shell.md` | 全局外壳线框图 |
| `wireframes/01-scenario-selection.md` | P1 场景选择线框图 |
| `wireframes/02-agent-dashboard.md` | P2 仪表盘线框图 |
| `wireframes/03-approval-dialog.md` | P3 审批模态线框图 |
| `wireframes/04-session-results.md` | P4 结果与 Memory 线框图 |
| `reviews/ROUND_01_REVIEW.md` | 本评审文件 |

实际使用的 Open Design skill 准确名称：**`Web Prototype`**（文档化模式，本轮不产出 HTML/CSS/JS）。
设计系统准确名称：**`Vercel`**（Open Design 包 `design-systems/vercel`）。

---

## 8. 未生成实现代码声明

本轮严格遵循 SPEC 阶段禁令，**未生成或修改任何**：Python、FastAPI、Jinja2、HTML、CSS、JavaScript、React、Node.js 项目、测试代码、CI/CD、打包或部署配置、CodeGuard 正式源代码。全部交付物为 Markdown（`.md`）设计资料与 ASCII 低保真线框图。

---

## 9. 下一步

- **本轮到此为止**：不自行连续迭代，不进入实现。
- **等待用户人工评审**，建议就 §4 的 C1–C8 逐项回复，尤其 C1（文档化模式是否认可）、C3（场景 A 终态）、C4（场景 B 超时行为）、C7（是否提供磁盘 `UI_DESIGN_BRIEF.md`）。
- 收到评审后，再进入第二轮设计修订或转实现阶段。
