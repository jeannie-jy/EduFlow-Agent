# EduFlow Web 前端

`web/` 目录包含 EduFlow 的 React 前端。已交付：全新 Landing 叙事页、Dijkstra 公开探索页、
统一项目工作台（三步流程：选择模块 → 教学计划审批 → 成果预览）、纸张质感主题系统（明暗双主题）、
完整的 FastAPI 后端对接层。

## 环境要求

- Node.js 20 或更高版本
- npm 10 或更高版本

## 安装与运行

在仓库根目录执行：

```bash
cd web
npm ci
npm run dev
```

打开 Vite 输出的地址，通常是 `http://127.0.0.1:5173/`。

如需让同一局域网内的其他设备访问：

```bash
npm run dev -- --host 0.0.0.0
```

全栈体验需要同时启动后端：

```bash
# 仓库根目录
./start.sh          # Linux/macOS
.\start.ps1         # Windows
```

## 质量检查

```bash
npm run typecheck    # TypeScript 类型检查（tsc -b，真实门禁）
npm run test         # Vitest（228 个测试，26 个文件）
npm run lint         # oxlint
npm run build        # 生产构建
```

完整验证命令：

```bash
npm run verify       # typecheck + test + build
```

## 当前架构

```text
src/
├─ app/                    路由（React Router）+ 应用级 Provider
├─ components/
│  ├─ layout/              应用外壳、页眉、侧边栏、主题切换
│  ├─ ui/                  通用 Base UI 组件（25+ 个）
│  ├─ workbench/           推演工作台组件
│  │   ├─ visual-objects/  DSL 视觉对象渲染器（14 种：数组/表格/代码块/节点/边/状态表/公式/链表等）
│  │   ├─ SandboxRenderer.tsx  交互推演 iframe 沙箱（宿主侧 Babel 编译 + React UMD 本地注入）
│  │   └─ StepIndicator.tsx    三步流程步骤指示器
│  └─ effects/             特效组件（生成边框等）
├─ features/
│  ├─ auth/                认证（登录/注册，当前为临时占位）
│  ├─ demo/                Dijkstra 交互演示（状态机 + 播放器 + 时间线）
│  ├─ explore/             公开探索页（/explore/dijkstra）
│  ├─ landing/             首页（叙事结构 / 产品原理 / 交互案例 / 使用场景 / 模板库）
│  └─ modules/             模块化产出（选择器 / 进度 / 结果面板：思维导图/卡片/推演/小练习/对比/误区/路径/沙箱/视频）
├─ pages/                  4 个路由页面（Dashboard / ProjectWorkspace / TemplateBrowser / NotFound）
├─ templates/              交互推演沙箱模板（冒泡排序等，供测试与 LLM 生成参考）
├─ services/               API 客户端 + SSE + 8 个服务模块
├─ lib/                    工具函数库（auth 模块 + utils）
├─ styles/                 全局样式（纸张主题 tokens + 推演舞台动画 + reduced-motion）
├─ test/                   公共测试配置和 MSW Mock 处理器
├─ types/                  第三方库类型声明（@babel/standalone 等）
└─ theme/                  明暗主题持久化（localStorage + 系统偏好检测）
```

## 后端对接

`services/` 目录提供完整的 API 层对接 FastAPI 后端（8 个服务模块 + SSE 连接管理）：

| 服务 | 端点 |
|---------|-----------|
| `projects.ts` | `POST /api/projects`、`GET /api/projects`、`GET /api/projects/{id}` |
| `generate.ts` | `POST /generate`（action=full/plan_only/modules）、SSE 流、HITL approve/reject、模块列表/单模块重生成 |
| `frames.ts` | `GET frames`、`PUT frames/{fid}`、`POST lock` |
| `parameters.ts` | `GET parameters`、`POST recompute` |
| `export.ts` | `POST export/manim`、`GET /api/export/{job_id}`、`GET download/{filename}` |
| `knowledge.ts` | `POST knowledge/search`、`GET knowledge/templates` |
| `versions.ts` | `POST versions`、`GET versions`、`POST restore` |
| `sse.ts` | SSE 连接管理器（自动重连，模块事件分发） |

## 路由状态

| 路径 | 说明 |
|------|------|
| `/` | 落地页（叙事 / 产品原理 / 交互案例 / 使用场景 / 模板库） |
| `/explore/dijkstra` | 公开 Dijkstra 交互探索页 |
| `/login` / `/register` | 认证页面（当前为临时占位） |
| `/app` | 工作台（项目列表 + 状态筛选 + 分页 + 删除） |
| `/app/new` | 重定向到 `/app/project/_new`（新建模式） |
| `/app/project/:projectId` | 统一项目工作台（三步流程：select → plan → results） |
| `/app/project/_new` | 新建推演（输入主题 + 勾选模块 → 生成 → 审批 → 成果） |
| `/app/templates` | 知识模板浏览器（搜索 + 学科/难度筛选） |

> 旧版 `?tab=plan|play|edit|export` 参数已废弃（四 Tab 架构被三步流程取代），
> 历史链接由 `RedirectToTab` 重定向。

## 交互推演（interactive_demo 模块）

- LLM 生成的 React JSX 代码在 `SandboxRenderer` 的 iframe 沙箱中运行
- JSX 编译在**宿主侧**完成（Babel standalone，classic runtime），iframe 只接收编译后的 JS；
  React UMD 从 node_modules 本地注入（不依赖 unpkg CDN，规避网络不可达导致的空白）
- 模板参考：`src/templates/bubbleSortDemo.ts`（三段式布局 + 水平柱状图 + 状态色 + 按钮组）

## 主题行为

- 默认使用浅色主题（纸张质感：`--background` / `--canvas-background` / `--graph-*` / `--interactive` 等语义 tokens）。
- 用户选择通过 `localStorage` 持久化，支持跟随系统偏好。
- 切换主题不重置当前路由或推演帧。
- 新增颜色应使用 `src/styles/globals.css` 中的语义变量，不应硬编码（`--info`/`--error`/`--code-bg` 等已就绪）。
- 已适配 `prefers-reduced-motion`：减弱动画用户自动降级为 opacity 过渡。

## 安全

- **Content-Security-Policy**：`index.html` 配置了 CSP meta 标签，限制脚本/样式/字体/图片/连接源。
- **认证**：`lib/auth.ts` 仅用于 UI 状态缓存（localStorage），**刻意占位**、不作为安全边界；
  后端认证就绪后替换为 HttpOnly cookie + `/api/auth/me`。

## Mock 边界

`workbench/simulation-model.ts` 中的本地 Dijkstra 推演帧作为公开演示与测试夹具
（`SimulationGraph` 供 DijkstraDemo 使用）；模块化产出（含交互推演）一律来自后端 `module_outputs`。
