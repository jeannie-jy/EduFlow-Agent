# EduFlow Web 前端

`web/` 目录包含 EduFlow 的 React 前端。已交付：全新 Landing 叙事页、Dijkstra 公开探索页、教学推演工作台（四 Tab）、纸张质感主题系统（明暗双主题）、完整的 FastAPI 后端对接层。

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
npm run typecheck    # TypeScript 类型检查
npm run test         # Vitest（130 个测试，17 个文件）
npm run lint         # oxlint
npm run build        # 生产构建
```

完整验证命令：

```bash
npm run verify
```

## 当前架构

```text
src/
├─ app/                    路由（React Router）+ 应用级 Provider
├─ components/
│  ├─ layout/              应用外壳、页眉、侧边栏、主题切换
│  ├─ ui/                  通用 Base UI 组件（25+ 个）
│  ├─ workbench/           工作台推演模型和可视化
│  │   └─ visual-objects/  DSL 视觉对象渲染器（数组/表格/代码块/节点/边/状态表/公式/链表等）
│  ├─ FileUploader.tsx      拖拽文件上传 + 主题提取
│  └─ FeedbackPanel.tsx     帧级反馈：评分/纠错/建议
├─ features/
│  ├─ auth/                认证（登录/注册，当前为临时占位）
│  ├─ demo/                Dijkstra 交互演示（状态机 + 播放器 + 时间线）
│  ├─ explore/             公开探索页（/explore/dijkstra）
│  └─ landing/             首页（叙事结构 / 产品原理 / 交互案例 / 使用场景 / 模板库）
├─ pages/                  5 个路由页面（Dashboard / NewProject / ProjectWorkspace / TemplateBrowser / NotFound）
├─ services/               API 客户端 + SSE + 8 个服务模块
├─ lib/                    工具函数库（auth 模块 + utils）
├─ styles/                 全局样式（纸张主题 tokens + 推演舞台动画 + reduced-motion）
├─ test/                   公共测试配置和 MSW Mock 处理器
└─ theme/                  明暗主题持久化（localStorage + 系统偏好检测）
```

播放器优先使用后端 LLM 生成的 DSL，后端不可用时自动降级到本地确定性模型（Dijkstra 演示）。

## 后端对接

`services/` 目录提供完整的 API 层对接 FastAPI 后端（8 个服务模块 + SSE 连接管理）：

| 服务 | 端点 |
|---------|-----------|
| `projects.ts` | `POST /api/projects`、`GET /api/projects`、`GET /api/projects/{id}` |
| `generate.ts` | `POST /api/projects/{id}/generate`、SSE 流、`POST /regenerate` |
| `frames.ts` | `GET frames`、`PUT frames/{fid}`、`POST lock` |
| `parameters.ts` | `GET parameters`、`POST recompute` |
| `export.ts` | `POST export/manim`、`GET /api/export/{job_id}`、`GET download/{filename}` |
| `knowledge.ts` | `POST knowledge/search`、`GET knowledge/templates` |
| `versions.ts` | `POST versions`、`GET versions`、`POST restore` |
| `sse.ts` | SSE 连接管理器（含自动重连） |

## 路由状态

| 路径 | 说明 |
|------|------|
| `/` | 落地页（叙事 / 产品原理 / 交互案例 / 使用场景 / 模板库） |
| `/explore/dijkstra` | 公开 Dijkstra 交互探索页 |
| `/login` / `/register` | 认证页面（当前为临时占位） |
| `/app` | 工作台（项目列表 + 状态筛选 + 分页 + 卡片式删除） |
| `/app/new` | 新建推演（自然语言 + 文件上传） |
| `/app/project/:projectId` | 统一项目工作台（?tab=plan\|play\|edit\|export 四 Tab 切换） |
| `/app/project/:projectId?tab=plan` | 教学计划生成与审批（SSE 流式进度 + HITL） |
| `/app/project/:projectId?tab=play` | 交互播放器（可视化舞台 + 逐帧播放 + 键盘快捷键） |
| `/app/project/:projectId?tab=edit` | 帧编辑器（可视化对象/状态快照 JSON 编辑 + 锁定 + 重生成 + 版本管理） |
| `/app/project/:projectId?tab=export` | 导出中心（画质/FPS 配置 + 视频渲染 + 进度轮询 + 在线预览 + 产物下载） |
| `/app/templates` | 知识模板浏览器（搜索 + 学科/难度筛选） |

架构和开发约定见[设计文档](../docs/design/智能教学推演系统设计文档.md)，API 契约见[开发任务与接口规范](../docs/开发任务与接口规范.md)。

## 主题行为

- 默认使用浅色主题（纸张质感：`--paper` / `--canvas` / `--graph-*` tokens）。
- 用户选择通过 `localStorage` 持久化，支持跟随系统偏好。
- 切换主题不重置当前路由或推演帧。
- 新增颜色应使用 `src/styles/globals.css` 中的语义变量，不应硬编码。
- 已适配 `prefers-reduced-motion`：减弱动画用户自动降级为 opacity 过渡。

## 安全

- **Content-Security-Policy**：`index.html` 配置了 CSP meta 标签，限制脚本/样式/字体/图片/连接源。
- **认证**：`lib/auth.ts` 仅用于 UI 状态缓存（localStorage），不作为安全边界。后端认证就绪后替换为 HttpOnly cookie。

## Mock 边界

`workbench/simulation-model.ts` 中的本地 Dijkstra 推演帧既作为默认演示体验，也作为确定性测试夹具。后端可达时，播放器使用服务端 DSL；离线时自动降级到本地模型。
