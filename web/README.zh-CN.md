# EduFlow Web 前端

[English](README.md) | 简体中文

`web/` 目录包含 EduFlow 的 React 前端。当前已交付一个纯前端的 Dijkstra 教学工作台，包括响应式图谱、同步逐帧播放、状态检查器，以及可持久化的浅色/深色主题。

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

## 质量检查

```bash
npm run typecheck
npm run test
npm run lint
npm run build
```

完整验证命令：

```bash
npm run verify
```

`verify` 会依次运行类型检查、全部 Vitest 测试和生产构建。Lint 单独保留，以便开发者明确看到警告。

## 当前架构

```text
src/
├─ app/                    路由和应用级 Provider
├─ components/
│  ├─ brand/               EduFlow 品牌资源
│  ├─ effects/             可选装饰动效
│  ├─ layout/              应用外壳和侧边栏
│  ├─ ui/                  通用 Shadcn/Base UI 组件
│  └─ workbench/           Dijkstra 工作台和推演模型
├─ pages/                  页面级路由状态
├─ test/                   公共测试配置
└─ theme/                  浅色/深色主题及持久化
```

Dijkstra 演示由本地确定性模型生成。目前没有后端请求、身份认证、项目持久化或 AI 生成接口。

## 路由状态

| 路径 | 状态 |
| --- | --- |
| `/` | 已完成 Dijkstra 工作台 |
| `/new` | 占位页 |
| `/project/demo/plan` | 占位页 |
| `/project/demo/edit` | 占位页 |
| `/project/demo/play` | 占位页 |
| `/project/demo/export` | 占位页 |
| `/templates` | 占位页 |

架构和开发约定见[前端架构与开发指南](../docs/前端架构与开发指南.md)，未完成事项见[前端后续工作](../docs/前端后续工作.md)。

## 主题行为

- 默认使用浅色主题。
- 用户选择会保存到浏览器本地存储。
- 切换主题不会重置当前路由或推演帧。
- 新增颜色应使用 `src/styles/globals.css` 中的语义变量，不应硬编码。

## Mock 边界

本地推演帧是有意保留的演示数据，不是 API Mock Server。接入后端时，应将接口契约和传输逻辑放在 React 组件之外，并保留本地模型作为开发降级方案和确定性测试夹具。

