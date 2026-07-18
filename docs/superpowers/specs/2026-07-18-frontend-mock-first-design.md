# EduFlow-Agent 前端 Mock-First MVP 设计

**日期：** 2026-07-18

**状态：** 已确认，视觉系统待项目海报映射

**适用范围：** `web/` 前端应用、前后端数据契约、Mock 服务、交互式播放器与教师编辑器

## 1. 背景与目标

EduFlow-Agent 当前处于需求分析与架构设计阶段，仓库尚无前端或后端实现。现有文档已定义 Web 产品形态、主要页面、REST/SSE 接口和 RenderScript DSL，但部分字段、路由数量和动画类型仍不一致。

本设计的目标是在后端不可用时，先交付一个可独立运行、可测试、可演示，并能平滑切换到真实 API 的前端 MVP。第一条端到端链路为：

```text
工作台 → 新建推演 → 模拟生成进度 → 教学计划确认 → 逐帧播放器 → 教师编辑器
```

首批演示数据使用冒泡排序和 Dijkstra。视频导出、完整视觉对象集合、反馈闭环和版本对比在核心链路稳定后迭代。

## 2. 范围

### 2.1 首期包含

- React、TypeScript、Vite 前端工程及质量工具。
- 工作台、新建推演、教学计划确认、播放器和教师编辑器。
- 模板库与导出中心的可访问路由及明确空状态。
- REST API Mock、生成进度 Mock 和浏览器内演示数据持久化。
- RenderScript 前端领域模型、运行时校验和后端字段适配层。
- 5 种首批视觉对象：`node`、`edge`、`array`、`table`、`code_block`。
- 4 种首批动画：`appear`、`highlight`、`update_value`、`move`。
- 播放、暂停、逐帧跳转、倍速、讲解文本、状态表和参数面板。
- 教师对帧、讲解、画面对象、动画和锁定状态的低代码编辑。
- 组件测试、契约测试和关键用户流程端到端测试。

### 2.2 首期不包含

- 真实用户认证、学校统一身份认证和角色权限系统。
- 真实 Agent、数据库、文件解析、Manim Worker 或视频下载。
- 直接编辑原始 DSL JSON。
- 多人协作、班级管理、作业派发和学习进度追踪。
- 完整 14 种视觉对象、完整动画集合和通用本地算法重算。
- 生产级历史版本管理；浏览器快照仅服务于演示和测试。

## 3. 技术架构

采用单页 CSR 应用：

- React 18、TypeScript、Vite。
- Tailwind CSS 与 shadcn/ui 构成唯一基础组件和主题系统。
- React Router 管理页面路由。
- TanStack Query 管理项目、帧和生成任务等远端状态。
- Zustand 管理播放器状态、选中对象和未保存的编辑草稿。
- React Hook Form 管理属性面板表单。
- Zod 校验 API 响应、RenderScript 和编辑输入。
- MSW 拦截正式 API 路径并模拟成功、延迟和错误场景。
- React Flow 渲染图和树类对象；DOM/SVG 渲染数组、表格和代码块。
- Motion 或等价声明式动画库执行对象过渡。
- Vitest、Testing Library 和 Playwright 分别承担单元、组件和端到端测试。

前端分为五层：

```text
页面与功能模块
    ↓
播放器 / 编辑器领域状态
    ↓
RenderScript 解释器与渲染注册表
    ↓
Repository 与契约适配器
    ↓
MSW Mock 或真实 HTTP/SSE 服务
```

页面和组件不得直接读取 Mock fixture。它们只依赖 Repository 接口，因此切换真实后端时只替换数据来源和字段适配，不修改业务组件。

### 3.1 基础组件治理

shadcn/ui 是第一版唯一的基础组件来源。按钮、输入框、表单字段、卡片、导航、侧栏、标签页、弹窗、抽屉、提示、徽章、表格、骨架屏、加载状态和空状态必须优先使用 shadcn 组件及其内置变体，不得从其他组件库引入同类基础组件。

组件实现遵守以下规则：

- 使用 shadcn CLI 初始化 Vite 工程并管理 registry 组件，不手工复制 shadcn 源码。
- preset、基础色、字体和图标库在项目海报到位后通过视觉映射确定，并在开始编码前写入设计系统。
- 颜色使用 `background`、`foreground`、`primary`、`muted`、`accent`、`destructive` 等语义变量，不在业务组件中硬编码品牌色。
- 表单使用 `FieldGroup`、`Field` 和对应控件；空状态使用 `Empty`；加载使用 `Skeleton` 或 `Spinner`；通知使用 `sonner`。
- 第三方 registry 组件安装前必须预览差异，安装后必须检查源码、依赖、导入别名、图标来源和组件组合规范。

### 3.2 外部特效治理

Aceternity UI、Magic UI 和 Uiverse 只作为特效来源，不形成第二套基础组件体系。允许采用背景纹理、光效边框、文字揭示、进入过渡、悬停反馈、进度表现和状态切换；不得采用其按钮、表单、卡片、导航或弹窗替代 shadcn 组件。

第一版使用以下动态预算：

- 全站目标为约 6–10 个可复用特效组件，最终数量根据项目海报的视觉密度调整；该范围是设计预算，不是机械配额。
- 同一屏幕同时出现的持续显著动效不超过 2 个；用户操作触发的短暂微动效不计入这一数量。
- 首页、工作台和新建流程可以使用更强的视觉焦点；教师编辑器和播放器主画布以教学内容清晰度为优先。
- 相同效果跨页面复用，不为每个页面引入互不相关的动画语言。
- 所有持续动画必须支持 `prefers-reduced-motion`，并在 375、768、1024 和 1440 像素宽度检查布局和性能。
- 外部特效统一放在 `src/components/effects/`，按来源记录上游链接、许可证、依赖和本地修改；不得直接散落在页面目录。
- Aceternity UI 和 Magic UI 优先通过 shadcn registry 引入；Uiverse 组件人工移植后必须转换为 React、Tailwind 语义变量和项目图标体系。

项目海报到位后，Product Design 负责提取视觉目标，UI/UX Pro Max 生成并持久化设计系统，shadcn 负责基础组件与 registry，Frontend Design 负责生产级实现。任何外部特效只有在能够强化教学层级、生成状态或操作反馈时才保留。

## 4. 路由与页面

```text
/                         工作台
/new                      新建推演
/project/:id/plan         教学计划确认
/project/:id/edit         教师编辑器
/project/:id/play         交互式播放器
/project/:id/export       导出中心
/templates                知识点模板库
/*                        404 页面
```

现有任务文档所称“8 个页面”在本设计中解释为 7 条业务路由加 1 个 404 页面。系统设置不进入首期范围。

## 5. 数据契约与 Mock 策略

### 5.1 领域模型

前端内部只使用一套 camelCase 领域模型，包括：

- `Project`
- `TeachingPlan`
- `RenderScript`
- `RenderFrame`
- `VisualObject`
- `Animation`
- `InteractionHook`
- `Parameter`
- `QualityReport`
- `ApiError`

API 的 snake_case 字段由适配器转换。当前文档中的差异按以下规则收敛：

| 外部字段 | 前端领域字段 |
|---|---|
| `type` 或 `param_type` | `paramType` |
| `default` 或 `default_value` | `defaultValue` |
| `current_value` | `currentValue` |
| `recompute_scope` | `recomputeScope` |
| `frame_id` | `frameId` |
| `state_snapshot` | `stateSnapshot` |
| `visual_objects` | `visualObjects` |
| `interaction_hooks` | `interactionHooks` |

适配器对兼容字段只负责读取；发送请求时固定使用接口规范中的正式 snake_case 字段。后端联调前，双方应将这些字段固化为共享 OpenAPI 或 JSON Schema。

### 5.2 Mock 行为

MSW 使用与正式后端完全相同的 `/api` 路径，覆盖：

- 项目创建、列表和详情。
- 启动生成和生成进度流。
- 帧读取、更新、锁定和局部重生成。
- 参数读取和重算。
- 导出任务创建和状态查询。
- 标准错误响应、404、409、422 和 500 场景。

生成进度模拟 `planning`、`generating`、`validating`、`done` 和 `error`。`done` 事件只表示流程完成；页面随后重新获取项目详情得到最新 DSL，避免依赖 SSE 是否携带完整 DSL 的文档差异。

教学计划确认首期采用前端领域接口 `saveTeachingPlan(projectId, plan)`。Mock 实现保存计划；真实后端联调前必须补充对应 REST 接口，建议为 `PUT /api/projects/{id}/teaching-plan`。

Mock 数据默认存于内存，演示模式同步到带 schema 版本号的浏览器存储。测试运行时重置为固定 fixture，保证用例可重复。

## 6. 渲染内核与播放器

### 6.1 共享渲染内核

播放器和教师编辑器共享同一个 RenderScript 解释器。渲染器使用注册表按 `visualObject.type` 分派组件；未知类型显示安全占位，不导致整帧崩溃。

```text
RenderScript
  → Frame Runtime
  → Object Renderer Registry
  → Animation Executor
  → Frame Canvas
```

首批对象与实现：

| 类型 | 实现 |
|---|---|
| `node`、`edge` | React Flow |
| `array` | DOM Flex/Grid |
| `table` | HTML Table |
| `code_block` | 代码高亮组件 |

首批动画为 `appear`、`highlight`、`update_value` 和 `move`。其他动画在契约中允许出现，但由安全占位记录“不支持的动画”，不执行猜测行为。

### 6.2 播放状态机

播放器状态为：

```text
IDLE → PLAYING ↔ PAUSED
           ↓
        WAITING
           ↓
       RECOMPUTING → PAUSED
```

- 帧含交互钩子时进入 `WAITING`。
- 本地参数变更更新当前帧草稿；影响全部帧的参数通过 Repository 发起重算。
- 动画完成后才提交下一帧稳定状态。
- 切换帧时预读取相邻帧，目标响应时间小于 300ms。

## 7. 教师编辑器

### 7.1 模式关系

教师编辑器不是独立渲染实现，而是共享播放器内核的编辑模式：

```text
共享 Render Engine
├── Player Mode：播放、参数交互、反馈入口
└── Editor Mode：Player 能力 + 帧管理、属性编辑、锁定和重生成
```

### 7.2 布局

- 左侧：帧列表、帧状态、质量问题、锁定状态。
- 中间：共享画布，可选择和拖动画面对象。
- 右侧：基本信息、画面对象、状态数据、动画和质量问题表单。
- 底部：时间轴、播放控制、保存状态和局部重生成入口。

### 7.3 编辑能力

首期支持：

- 修改帧标题、学习目标和讲解文本。
- 修改对象标签、位置、颜色、尺寸、边线和可见性。
- 用结构化表单编辑 `stateSnapshot`。
- 调整动画顺序、类型、目标、持续时间和参数。
- 帧选择、复制、删除、拖拽排序、锁定和解锁。
- 对当前帧、连续帧或从当前帧到结尾发起局部重生成。
- 显示质量问题，并在可能破坏帧间一致性时标记需要校验。

对象位置修改默认只作用于当前帧。跨帧应用必须由教师显式选择“应用到包含该对象的后续帧”。

### 7.4 草稿与保存

编辑采用“草稿—校验—保存”流程：

```text
选择帧 → 建立本地草稿 → 编辑 → Zod 校验 → 显式保存
       → Repository/API → 更新 Query Cache → 标记后续校验状态
```

- 切换存在未保存修改的帧时必须确认保留或放弃。
- 标题和讲解可在后续迭代加入延迟自动保存；首期统一显式保存。
- 删除仍被动画引用的对象、动画指向不存在的对象或持续时间非法时阻止保存。
- 页面内撤销/重做只覆盖未保存草稿；历史版本由后端版本 API 负责。

### 7.5 锁定与局部重生成

锁定帧可查看和播放，但默认禁止编辑。局部重生成请求必须携带锁定帧 ID，Mock 和真实后端都不得覆盖锁定帧。

可选范围：

- `single_frame`：仅当前帧。
- `frame_range`：连续选中帧。
- `from_frame`：从当前帧到结尾。

Mock 重生成使用替代 fixture 模拟新结果，并验证锁定帧内容保持不变。跨越锁定帧时，锁定帧的 `stateSnapshot` 被视为后续计算边界。

## 8. 错误处理

- 全局错误边界处理未知渲染异常，并保留返回工作台入口。
- 页面分别呈现加载、空数据、无权限、网络错误和重试状态。
- 契约校验失败展示字段路径和可读说明，不将无效数据送入渲染器。
- HTTP 409 显示锁定冲突并刷新最新帧。
- SSE 断开后显示重连或返回项目详情选项，不伪造完成状态。
- 未支持的 DSL 对象或动画降级为占位与警告，不阻断其他对象。
- 编辑失败保留本地草稿，避免教师输入丢失。

## 9. 测试与验收

### 9.1 单元与契约测试

- snake_case API 数据正确转换为领域模型。
- 文档兼容字段能被读取，发送请求只使用正式字段。
- 非法 RenderScript 被拒绝并返回精确字段路径。
- 播放状态机在播放、暂停、等待和重算间正确转换。
- 渲染注册表对未知类型安全降级。

### 9.2 组件测试

- 5 种对象正确渲染，4 种动画正确执行。
- 时间轴、倍速、前后帧和状态表同步。
- 修改讲解文本后，共享播放器展示新文本。
- 拖动对象只更新目标帧的位置。
- 锁定帧不能编辑，也不能被 Mock 重生成覆盖。
- 删除仍被动画引用的对象时阻止保存。
- 409 冲突、契约错误和保存失败均保留草稿并给出提示。

### 9.3 端到端验收

1. 从工作台进入新建页，输入“演示冒泡排序”。
2. 创建项目并看到分阶段生成进度。
3. 查看和修改教学计划后确认生成。
4. 在播放器逐帧播放数组比较和交换过程。
5. 进入教师编辑器修改讲解、拖动对象并保存。
6. 锁定一帧后执行局部重生成，锁定帧保持不变。
7. 刷新页面，演示项目和已保存编辑能够恢复。

Dijkstra fixture 用于补充验证图节点、边、状态表和全帧重算流程。

## 10. Git 分支与交付顺序

长期分支为 `main` 和 `develop`。功能分支从最新 `develop` 创建，完成后通过 PR 合并回 `develop`，阶段验收后再合并到 `main`。

推荐顺序：

1. `feature/frontend-foundation`
2. `feature/frontend-contract-mocks`
3. `feature/frontend-create-flow`
4. `feature/frontend-renderer-core`
5. `feature/frontend-teacher-editor`
6. `feature/frontend-advanced-renderers`
7. `feature/frontend-export-center`
8. `feature/frontend-feedback-versioning`
9. `feature/frontend-ui-polish`

前五个分支构成首个可演示闭环。每个功能分支必须包含对应测试，并保持可独立评审。存在依赖的分支依次合并；只有页面空状态、文档等低耦合工作适合并行。

## 11. 接口定稿前置项

真实后端联调前必须完成以下收敛：

1. 将路由数量明确为 7 条业务路由加 404，或新增正式业务页面。
2. 固化 Parameter 的 `param_type`、`default_value` 和 `current_value`。
3. 统一动画枚举；首期支持集合与完整允许集合分别版本化。
4. 增加教学计划读取和保存接口。
5. 明确生成 SSE 的事件载荷；前端保持完成后重新获取项目详情。
6. 用 OpenAPI 或 JSON Schema 生成或校验前后端共享契约。

## 12. 完成标准

当以下条件全部满足时，Mock-First 前端 MVP 设计目标完成：

- 无后端服务时可启动并完成核心用户链路。
- 冒泡排序和 Dijkstra 均可逐帧播放。
- 教师可以编辑、保存、锁定和模拟重生成帧。
- UI 不直接依赖 fixture，切换真实 API 不需要重写页面和渲染组件。
- 自动化测试覆盖核心契约、播放器状态机和教师编辑路径。
- 所有页面具有明确的加载、空、错误和恢复状态。
