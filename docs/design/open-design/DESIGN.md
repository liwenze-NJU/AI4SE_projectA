# CodeGuard Harness — WebUI 设计规格 (DESIGN.md)

> 阶段：SPEC 规约阶段（第一版，待人工评审）
> 产出范围：仅设计文档 / 信息架构 / 低保真线框图 / 静态设计图 / 评审资料。
> 本轮**不**生成任何 HTML / CSS / JavaScript / React / Python / FastAPI / Jinja2 / 测试 / CI / 打包 / CodeGuard 正式源代码。

---

## 0. 文档定位与来源说明

- 本文档为 CodeGuard Harness 在线 WebUI 的**视觉与交互设计规格**，服务于"安全 Mock Demo"场景。
- 简报来源：用户请求中给出的"一、项目背景"至"八、结束条件"，等价于 `UI_DESIGN_BRIEF.md` 全文。**磁盘上 `README.md` 与 `UI_DESIGN_BRIEF.md` 当前不存在**（工作目录仅含 `.od-skills/` 脚手架）。后续若用户提供磁盘文件，以磁盘文件为准并覆盖本文档中冲突的条款。
- 设计系统来源：Open Design 内置的 **Vercel** 设计系统包（`tokens.css` + `DESIGN.md`），已在本轮系统提示中完整注入，作为色彩、排版、间距、组件的**唯一约束契约**。

---

## 1. 设计目标

面向教师、助教、开发者三类受众，WebUI 必须让观看者**在 5 分钟内**理解 Coding Agent Harness 的工作机制：

1. **Agent = LLM + Harness**：LLM 只决定"下一步动作"，Harness 负责上下文、治理、工具执行、反馈、停机。界面需把"决策方"与"执行/治理方"在视觉上分离。
2. **治理护栏**：危险动作会被 `BLOCK` 或进入 `REQUEST_APPROVAL`，护栏决策以**状态标签 + 图标 + 文字**三重表达。
3. **测试反馈闭环**：第一次失败 → 结构化反馈分类 → 驱动 Agent 改变动作 → 第二次通过，必须以时间线完整回放。
4. **显式状态机**：9 个运行态 + 4 个终态必须始终可见，当前态高亮，不可只靠颜色区分。
5. **安全 Mock**：每一屏持续显示"安全 Mock 演示模式"，不出现真实 Shell / 文件系统 / LLM / API Key / 凭据输入。

设计语气：**工程化的克制**——大量留白、近白底近黑字、阴影即边框、单色为主、色彩仅为功能语义服务。与 Vercel 设计哲学一致，但**不复制 Vercel 的 Logo / 商标 / 部署业务页面**；所有产品语汇替换为 CodeGuard 的治理语义。

---

## 2. Vercel Design System 的采用方式

### 2.1 实际使用的 Open Design skill 与设计系统名称

- **实际使用的 Open Design skill 准确名称**：`Web Prototype`（Open Design 内置 skill，路径 `.od-skills/web-prototype-75fd6bb9c9/`）。
  - **本轮使用模式**：**文档化模式（documentation-only）**。因用户规约阶段明确禁止产出 HTML / CSS / JS，`Web Prototype` 的"复制 seed → 粘贴 layouts → 产出 HTML"流程在本轮**不执行其 HTML 产出步骤**；仅采用其"先读 seed/系统、再粘贴布局、再自检"的**方法论**，将成果落到 Markdown 设计文档与 ASCII 线框图。skill 中"防 AI-slop"的精神（先吃透设计系统、不凭空写 CSS、先选布局再写文案）通过"绑定 Vercel tokens、先定信息架构再填内容"在本轮复现。
  - **预读调整**：skill 要求 pre-flight 读 `assets/template.html` / `references/layouts.md` / `references/checklist.md`。本轮因禁止 HTML 产出，未加载 HTML 模板；改为以系统提示中已**完整注入的 Vercel `DESIGN.md` + `tokens.css`**作为视觉契约来源，等价满足"先吃透设计系统再动笔"的意图。
- **Vercel Design System 准确名称**：`Vercel`（Open Design 设计系统包 `design-systems/vercel`，契约文件 `tokens.css` + `DESIGN.md`，组件清单 `components.manifest.json`）。本设计严格使用其 `:root` 令牌，不在令牌块外引入裸 hex。

### 2.2 采用的规范（逐条）

| Vercel 规范 | 本设计的采用方式 |
|---|---|
| 近白底近黑字 (`--bg #fff` / `--fg #171717`) | 全局画布与卡片表面；提供 ~16:1 对比度，天然适配教室投影与高对比度要求。 |
| 阴影即边框 (`--elev-ring` `0 0 0 1px var(--border)`) | 所有分隔线、卡片边缘、表头行均用阴影边框，不写 `border`。 |
| 多层卡片阴影 (`--elev-raised`，含内层 `#fafafa` 微光) | 状态机面板、执行轨迹卡片、审批卡使用完整四层阴影，保留"建造感而非漂浮感"。 |
| 三权重体系 (400/500/600，无 700 正文) | 正文 400、UI/交互 500、标题/强调 600。仅 7px 微徽章用 700。 |
| 负字距随字号收敛 (display -0.05em) | 大标题保留负字距；正文与投影场景适度放宽以保远读可读性（见 §4 调整）。 |
| Geist / Geist Mono + OpenType `liga` | 展示与正文用 Geist 栈，代码/技术标签/状态机节点用 Geist Mono；字体栈含系统回退，投影机无 Geist 仍可读。 |
| 色彩仅为功能 (workflow 红/粉/蓝仅用于管线阶段) | 借用"功能色"原则，但把 CodeGuard 的护栏/状态语义映射到 `--success/--warn/--danger/--accent`，**不**复用 Vercel 的 Ship/Preview/Deploy 业务色名。 |
| 药丸仅用于徽章/标签 (9999px)，主操作按钮不用药丸 | 状态标签、Mock 模式徽章用药丸；批准/拒绝按钮用 6px 圆角矩形，符合"主操作非药丸"。 |
| 焦点环 `2px solid --accent` | 所有交互元素键盘焦点可见，支持投影演示中的键盘操作。 |
| 留白即设计 (节段 96/64/48px) | 仪表盘主区采用充裕纵向节律，避免信息堆叠。 |

### 2.3 因课堂投影与可访问性而调整的规范

| Vercel 默认 | 课堂/可访问性调整 | 理由 |
|---|---|---|
| 正文 16px / 说明 12px | 正文 ≥18px、说明 ≥14px（投影地板） | 1366×768 投影远读，16/12px 偏小；WCAG 与教室可读性要求更大字号。 |
| 内容最大宽 1200px | 仪表盘最大宽 ~1440px | 仪表盘需并列"状态机 / 执行轨迹 / 工具调用 / 护栏决策"多栏，1200px 过窄；仍保持 24px 侧边距。 |
| 单屏 ≤2 处强调色（装饰预算） | **装饰强调色仍 ≤2**；但**状态语义色（成功/警告/危险）不受此预算约束**，因其编码状态、属功能色 | Vercel 自身原则"色彩为功能而非装饰"；仪表盘多状态若限 2 色则无法表达，故把"状态色"明确豁免出装饰预算。 |
| 状态药丸以色为主 | **每个状态标签 = 色 + 图标 + 中文文字**，三重冗余 | 简报硬性要求"状态不能只通过颜色表达"。 |
| 状态文本用饱和令牌色 | 标签**文字**用加深的同色族（经 `color-mix` 派生），饱和令牌色用于图标/圆点/背景浅染 | `#16a34a/#eab308` 在白底上对比度不足以做正文文字；加深以满足 AA，同时不引入裸 hex（用 `color-mix(in oklab, var(--success), black 18%)` 等）。 |
| 短过渡 150–200ms + 软渐变 hero | **仅保留**状态切换的 ≤200ms 透明度/颜色过渡；**移除** hero 渐变洗、入场编排、视差 | 简报"不使用复杂动画"；投影与可访问性偏好减少动效。提供 `prefers-reduced-motion` 全关。 |
| 基础 Geist 负字距 -2.4px@48px | display 用 -0.03em～-0.05em，display 行高 1.15 | 极端压缩在投影远读下损失字形，适度放宽。 |

---

## 3. 色彩与状态语义

### 3.1 基础调色板（绑定 Vercel 令牌，不引入裸 hex）

| 角色 | 令牌 | 值 | 用途 |
|---|---|---|---|
| 页面/卡片底 | `--bg` / `--surface` | `#ffffff` | 全局画布、卡片 |
| 主文字 | `--fg` | `#171717` | 标题、正文、主交互文字 |
| 次文字 | `--fg-2` | `#4d4d4d` | 说明、轨迹描述 |
| 三级文字 | `--muted` | `#666666` | 标签、时间戳 |
| 占位/禁用 | `--meta` | `#808080` | 禁用态、空态提示 |
| 边框（阴影） | `--border` | `rgba(0,0,0,0.08)` | 阴影即边框 |
| 行内分隔 | `--border-soft` | `rgba(0,0,0,0.04)` | 轨迹内行分隔 |
| 强调/链接/焦点 | `--accent` | `#0070f3` | 链接、焦点环、进行态徽章浅染 |
| 成功 | `--success` | `#16a34a` | ALLOW / COMPLETED / 测试通过 |
| 警告 | `--warn` | `#eab308` | REQUEST_APPROVAL / LIMIT_REACHED / Mock 模式横幅 |
| 危险 | `--danger` | `#dc2626` | BLOCK / FAILED / 测试失败 |

> 文字色加深派生（不写裸 hex，运行时由 `color-mix` 生成，用于标签文字以满足 AA）：
> `--success-text: color-mix(in oklab, var(--success), black 22%)`；
> `--warn-text: color-mix(in oklab, var(--warn), black 28%)`；
> `--danger-text: color-mix(in oklab, var(--danger), black 14%)`。
> 浅染徽章背景：`--success-tint: color-mix(in oklab, var(--success), white 86%)`，警告/危险同理。

### 3.2 Agent 状态机语义映射

| 状态 | 语义色 | 图标 | 文字标签 | 视觉处理 |
|---|---|---|---|---|
| `INITIALIZING` | `--muted` 灰 | ◷ 沙漏 | 初始化中 | 节点灰圈，脉冲点 |
| `BUILDING_CONTEXT` | `--muted` 灰 | ▤ 堆叠 | 构建上下文 | 节点灰圈实心 |
| `DECIDING` | `--accent` 蓝 | ◇ 菱形 | 决策中 | 蓝色描边节点 |
| `GOVERNING` | `--accent` 蓝 | 🛡 护盾 | 治理评估 | 蓝色描边 + 护盾 |
| `AWAITING_APPROVAL` | `--warn` 黄 | ⏸ 暂停 | 等待审批 | 黄色填充 + 暂停条；整条时间线在此暂停 |
| `EXECUTING` | `--accent` 蓝 | ▶ 执行 | 执行工具 | 蓝色实心节点 |
| `VALIDATING` | `--accent` 蓝 | ✓ 验证 | 校验测试 | 蓝色描边 + 勾 |
| `FEEDING_BACK` | `--warn` 黄 | ↺ 回灌 | 反馈回灌 | 黄色描边 + 回环箭头 |
| `COMPLETED` | `--success` 绿 | ✓ | 已完成 | 终态绿色实心 + 绿色完成横线 |
| `FAILED` | `--danger` 红 | ✕ | 已失败 | 终态红色实心 |
| `CANCELLED` | `--meta` 灰 | ◌ | 已取消 | 终态灰色实心 |
| `LIMIT_REACHED` | `--warn` 黄 | ⇪ 上限 | 达到上限 | 终态黄色实心 |

护栏决策语义（与状态机 `GOVERNING` 节点联动）：

| 决策 | 语义色 | 图标 | 文字 | 含义 |
|---|---|---|---|---|
| `ALLOW` | `--success` | ✓ | 允许 | 动作安全，放行执行 |
| `BLOCK` | `--danger` | ⊘ | 阻止 | 路径逃逸/危险动作，硬阻止 |
| `REQUEST_APPROVAL` | `--warn` | ? | 待审批 | 有副作用但可能合法，需人工 |

> 三重冗余铁律：以上**每一项**都以 颜色 + 图标 + 中文文字 同时呈现；色彩仅作为冗余强化，单独抽离色彩仍可完整理解状态。色盲（红绿/红黄）场景下靠图标与文字区分 ALLOW/BLOCK/REQUEST_APPROVAL。

### 3.3 Mock 安全表达色

- **Mock 演示模式横幅**：背景 `color-mix(in oklab, var(--warn), white 80%)`（浅琥珀），文字 `--warn-text`，左侧 🛡/🔒 图标 + "安全 Mock 演示模式"，右侧灰字列明未连接项："未连接真实 Shell · 文件系统 · LLM · API Key · 凭据"。横幅为 sticky 顶部条，**不可关闭**，在四屏均常驻。
- **场景卡角标**：右上角药丸 `--warn-tint` 底 + `--warn-text` 文字 "确定性 Mock · 离线回放"。
- **Mock 数据标注**：所有伪路径/伪命令前缀 `MOCK` 标签（mono 字体，`--meta` 色），避免被误读为真实环境。

---

## 4. 字体层级（投影地板调整）

| 角色 | 字体 | 字号 | 权重 | 行高 | 字距 | 备注 |
|---|---|---|---|---|---|---|
| 页面标题/终态大字 | Geist | 40–48px | 600 | 1.15 | -0.03em ~ -0.05em | 仪表盘主标题、会话结果大状态 |
| 区段标题 | Geist | 28–32px | 600 | 1.2 | -0.02em | "执行轨迹""护栏决策"等 |
| 卡片标题 | Geist | 22–24px | 600 | 1.33 | -0.01em | 审批目标动作标题 |
| 正文大 | Geist | 20px | 400 | 1.7 | normal | 场景说明、风险原因叙述 |
| 正文 | Geist | 18px | 400 | 1.6 | normal | 描述、轨迹说明（投影地板） |
| UI/交互文字 | Geist | 16px | 500 | 1.5 | normal | 按钮、导航 |
| 说明/标签 | Geist | 14px | 400–500 | 1.5 | normal | 时间戳、元数据（投影地板，≥14） |
| 技术标签/状态机节点 | Geist Mono | 13–14px | 500 | 1.5 | normal | `DECIDING` 等态名，`tnum` 用于序号 |
| 代码/伪命令 | Geist Mono | 14–16px | 400 | 1.5 | normal | 工具调用、Mock 命令 |
| 微徽章 | Geist | 10–12px | 700 | 1 | normal | `text-transform: uppercase` 的 `MOCK` 角标 |

- OpenType：所有 Geist 文本 `font-feature-settings: "liga"`；Mono 技术标签另开 `"tnum"` 以对齐序号列。
- 字体栈：`--font-display/--font-body = "Geist","Geist Sans",-apple-system,"Segoe UI",Arial,sans-serif`；`--font-mono = "Geist Mono",ui-monospace,"SF Mono",...`。投影机未装 Geist 时回退到系统无衬线/等宽，仍满足可读性。
- 三权重铁律：正文 400、UI 500、标题 600；**禁止**正文 700。

---

## 5. 间距规则

- 基础网格 4px（`--space-1`）；节奏单位 8px（`--space-2`）。
- 结构刻度：`--space-1..12` = 4/8/12/16/20/24/32/48。
- 节段纵向节律：桌面 `--section-y-desktop: 96px`、平板 64px、手机 48px；仪表盘内部区块间 32px。
- 容器：仪表盘最大宽 1440px（调整），侧边距桌面 24px / 平板 16px / 手机 12px；登录/选择页保持 1200px。
- 组件内距：卡片 `--space-6`(24px) 内距、按钮 8px×16px、药丸 0×10px、表单行间 16px。
- 触达目标：可点击元素高度 ≥40px（桌面投影），主操作按钮 ≥44px。

---

## 6. 组件规范

> 组件形态参照 Vercel `components.manifest.json` 清单，语义替换为 CodeGuard。

### 6.1 按钮
- **主操作（批准）**：`background: var(--fg)`（#171717 黑）、白字、`--radius-sm` 6px、8×16 内距、hover 过渡到 `color-mix(in oklab, var(--fg), white 12%)`。用于"批准执行"。
- **次操作（拒绝/取消）**：白底 + `--elev-ring` 阴影边框、`--fg` 字、6px。用于"拒绝""关闭"。
- **危险操作（拒绝并终止）**：`background: var(--danger)`、白字、6px；或 ghost 变体（白底 + `--danger-text` 文字 + 红边）。用于"拒绝并停止 Agent"。
- **幽灵（查看详情）**：透明、`--accent` 文字、hover 加 `--accent` 下划线。
- 焦点：`--focus-ring` 2px `--accent`。禁用：`--meta` 字 + 0.5 透明度。
- **禁止**把主操作做成 9999px 药丸（药丸仅用于状态标签）。

### 6.2 卡片与面板
- 通用卡：白底、`--elev-raised` 四层阴影、`--radius-md` 8px、24px 内距。
- 图像/重点卡：`--radius-lg` 12px 顶部圆角 + `1px solid var(--border)` 边（仅在结构必要时用真边框，如截图容器）。
- hover：阴影由 `--elev-ring` 升至 `--elev-raised`，200ms。
- 仪表盘三栏面板（状态机 / 轨迹 / 工具+护栏）均用此卡。

### 6.3 状态药丸/徽章
- 9999px 药丸；背景为语义浅染（`--success-tint` 等），文字为加深派生（`--success-text` 等），左侧 6px 圆点用饱和令牌色，图标 + 中文文字。
- 三例：`ALLOW ✓ 允许`、`BLOCK ⊘ 阻止`、`REQUEST_APPROVAL ? 待审批`。
- Agent 终态药丸：`COMPLETED ✓ 已完成`（绿）、`FAILED ✕ 已失败`（红）、`CANCELLED ◌ 已取消`（灰）、`LIMIT_REACHED ⇪ 达到上限`（黄）。

### 6.4 状态机时间线（核心组件）
- 垂直时间线（桌面可转水平步进器，见 §6.5），节点圆 16px，连线 2px `--border`。
- 已完成态：节点实心语义色 + 连线实色；当前态：节点描边语义色 + 脉冲（≤200ms 透明度，可被 reduced-motion 关闭）；未到达态：节点空心 `--meta` + 虚线。
- 每节点：mono 态名（如 `GOVERNING`）+ 中文标签 + 状态药丸 + 可选时间戳（`tnum` mono）。

### 6.5 水平步进器（仪表盘顶部概览）
- 9 个运行态横向排列，当前态高亮放大 1.1×；4 个终态在末段以分支收敛呈现（COMPLETED 主路径，FAILED/CANCELLED/LIMIT_REACHED 为侧分支），用图标+文字区分。

### 6.6 审批对话框（模态）
- 遮罩 `--ds-overlay-backdrop-color hsla(0,0%,98%,1)` 半透明；
- 卡片居中、`--elev-raised`、`--radius-md` 8px、最大宽 560px；
- 结构：标题（目标动作 mono）+ 风险原因列表 + 影响范围卡 + 倒计时条（超时） + 三按钮（批准/拒绝/稍后）；
- 焦点陷阱、Esc=取消、Enter=聚焦按钮；倒计时为视觉条 + mono 数字，非纯动画。

### 6.7 执行轨迹列表
- 时间线行：左侧 mono 时间戳 + 态名药丸 + 右侧描述；行间 `--border-soft` 分隔；
- 工具调用展开行：mono 命令 + 入参（Mock 标注）+ 结果药丸；
- 失败行：`--danger` 左边条（4px）+ 失败类别药丸 + 诊断详情折叠区。

### 6.8 反馈闭环卡
- 三段式：① 第一次失败（红）→ ② 反馈分类（黄，类别药丸：编译/断言/超时/类型/导入等）→ ③ Agent 改变动作（蓝，回环箭头）→ 第二次通过（绿）。
- 用连线 + 编号箭头表达因果，不依赖动画。

### 6.9 导航/外壳
- sticky 顶栏：左侧 CodeGuard Harness 字标（非 Vercel logo）+ 当前场景名 + Mock 横幅；中部场景选择下拉；右侧运行态指示药丸 + "返回场景"次按钮。
- 底栏：mono 文本 "ScriptedMockLLM · 离线确定性回放 · 不接触真实环境"。

### 6.10 输入控件（受限）
- **不**设计自由 Shell 输入框、不设计 API Key 输入框。
- 仅：场景单选卡（选中态 `--elev-raised` + `--accent` 描边）、审批按钮组、轨迹折叠展开、可选"步进/暂停/重放"演示控件（控制 Mock 回放进度，非真实执行）。

---

## 7. 可访问性

1. **对比度**：正文 `#171717`/`#ffffff` ≈ 16:1（AAA）；状态标签文字用 `color-mix` 加深派生以满足 AA（≥4.5:1 正文、≥3:1 大字/UI 组件）；饱和令牌色仅用于图标/圆点/浅染背景（满足 WCAG 1.4.11 非文本对比 ≥3:1）。
2. **状态非色单一**：所有状态 = 色 + 图标 + 中文文字三重冗余；色盲友好。
3. **焦点可见**：所有交互 `--focus-ring` 2px `--accent`；对话框焦点陷阱；键盘可完成审批。
4. **动效**：仅 ≤200ms 颜色/透明度过渡；`@media (prefers-reduced-motion: reduce)` 全关动效；状态切换不以动效为唯一信号。
5. **触达目标**：主按钮 ≥44px、次交互 ≥40px。
6. **语义 HTML 基线**（实现期约束，本轮不产出）：`<main>/<nav>/<section>` 地标、`role="dialog"`、`aria-live="polite"` 用于状态机当前态变更播报、`aria-label` 标注图标按钮。
7. **投影适配**：1366×768 最小可视，1440×900 为理想演示分辨率；字号地板见 §4；高对比度模式（Windows 高对比度）下令牌仍可读。
8. **不依赖音效/震动**。

---

## 8. Mock 安全表达（贯穿全屏）

1. **常驻顶部 Mock 横幅**（§3.3）：不可关闭、四屏常驻、琥珀浅底 + 护盾图标 + 未连接项清单。
2. **场景卡角标**："确定性 Mock · 离线回放"。
3. **数据标注**：伪路径/伪命令加 `MOCK` mono 角标；路径以 `mock://workspace/...` 形式呈现，不出现真实盘符语义。
4. **无真实输入面**：不出现 Shell 命令输入框、不出现 API Key/凭据输入框；"工具调用"仅展示回放数据。
5. **底栏声明**：ScriptedMockLLM 离线确定性回放声明。
6. **演示控件语义**："步进/重放"仅控制 Mock 脚本进度，按钮文案明确为"演示步进"而非"执行命令"。

---

## 9. 最终实现技术约束（前瞻，本轮不实现）

> 以下为**未来实现轮**必须遵守的约束，本轮**仅记录、不产出代码**。

1. 单一自包含前端，不连真实环境：无真实 Shell、文件系统、LLM、API Key、Windows Credential Manager、用户本机环境的任何调用。
2. 全部数据来自 `ScriptedMockLLM` 的确定性离线回放（三个固定脚本对应三个 Mock 场景）；状态机迁移与护栏决策为脚本预设，非运行期计算。
3. 视觉严格绑定 Vercel `tokens.css` `:root` 令牌；令牌块外不出现裸 hex；色彩经 `color-mix` 派生。
4. 响应式：1366×768 起步，无横向滚动；仪表盘在小屏重排为单列（状态机 → 轨迹 → 工具+护栏 → 审批/结果）。
5. 可访问性达 AA：状态三重冗余、焦点可见、reduced-motion、语义地标、aria-live 播报当前态。
6. 不引入复杂动画；演示"步进"以离散状态切换实现，不依赖连续动画。
7. 不内嵌 Vercel Logo/商标/部署业务页面；产品语汇全量替换为 CodeGuard 治理语义。
8. 交付为可离线打开的静态资源（实现期由用户决定 HTML+CSS+vanilla JS 或轻量框架；本轮不预定，留待评审确认）。

---

## 10. 实际使用的 Open Design skill 名称（声明）

- **Skill**：`Web Prototype`（Open Design 内置 skill）——本轮以**文档化模式**使用（不产出 HTML/CSS/JS，符合 SPEC 阶段禁令）；采用其方法论（先读系统、先选布局再填文案、终末自检）。
- **设计系统**：`Vercel`（Open Design 设计系统包 `design-systems/vercel`，契约 `tokens.css` + `DESIGN.md`）。
- 采用/调整明细见 §2.2 / §2.3。
