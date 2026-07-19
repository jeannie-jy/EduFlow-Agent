# EduFlow-Agent

> 面向计算机科学教育的 Agent 教学推演系统，将抽象知识点转化为可交互、可解释的逐帧推演。

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)

## 当前状态

项目已从需求设计阶段进入前端原型实现阶段。

- 已完成：React 应用外壳、响应式侧边栏、默认浅色/可切换深色主题、Dijkstra 六节点互动推演、14 帧本地状态模型、播放控制、状态检查器和前端测试。
- 尚未完成：后端 API 接入、新建推演、教学计划确认、教师编辑器、独立播放器、模板库、导出中心、身份认证和项目持久化。
- 当前边界：`web/` 可独立运行；互动推演使用确定性的本地数据，不依赖后端。

完整缺口和优先级见[前端后续工作](docs/前端后续工作.md)。

## 技术概览

| 层次 | 当前技术 | 状态 |
| --- | --- | --- |
| 前端 | React 18、TypeScript、Vite、React Router | 已建立 |
| UI | Shadcn/Base UI、Tailwind CSS、Lucide | 已建立 |
| 图形推演 | `@xyflow/react` | Dijkstra 演示已完成 |
| 动效 | Motion，按需懒加载 | 已建立 |
| 前端测试 | Vitest、Testing Library、JSDOM | 已建立 |
| 后端/Agent | 以系统设计和接口规范为准 | 待接入 |
| 数据库 | PostgreSQL、pgvector、Redis | 待接入 |
| 视频导出 | Manim CE、FFmpeg | 待实现 |

## 快速启动前端

环境要求：Node.js 20+、npm 10+。

```bash
git clone https://github.com/jeannie-jy/EduFlow-Agent.git
cd EduFlow-Agent/web
npm ci
npm run dev
```

浏览器打开 Vite 输出的地址，通常为 `http://127.0.0.1:5173/`。

完整检查：

```bash
npm run verify
npm run lint
```

Windows PowerShell 也可从仓库根目录运行：

```powershell
npm --prefix web ci
npm --prefix web run dev
npm --prefix web run verify
npm --prefix web run lint
```

详细操作、目录职责和开发约定见[前端架构与开发指南](docs/前端架构与开发指南.md)；前端目录同时提供 [English README](web/README.md) 和[中文版 README](web/README.zh-CN.md)。

## 基础设施

后端开发需要时，可复制环境变量模板并启动本地基础设施：

```bash
cp .env.example .env
docker compose up -d
```

不要将真实密钥提交到仓库。当前纯前端预览不需要 `.env` 或 Docker。

## 文档索引

| 文档 | 说明 |
| --- | --- |
| [需求文档](docs/requirements/自主Agent教学推演系统_需求文档包_v1.md) | 用户故事、范围和验收边界 |
| [系统设计文档](docs/design/智能教学推演系统设计文档.md) | 完整技术方案 |
| [开发任务与接口规范](docs/开发任务与接口规范.md) | 前后端任务和接口约定 |
| [前端架构与开发指南](docs/前端架构与开发指南.md) | 前端启动、目录、测试和扩展方式 |
| [前端后续工作](docs/前端后续工作.md) | 未完成事项、优先级和完成标准 |
| [互动推演设计验收](design-qa.md) | 当前页面的视觉与交互验收记录 |
| [术语表](docs/GLOSSARY.md) | 中英文术语映射 |
| [贡献指南](CONTRIBUTING.md) | 分支、提交和评审规范 |

## 分支与提交

当前前端重设计工作位于 `codex/frontend-codex-redesign`。提交前请先运行验证，使用 Conventional Commits，并通过 Pull Request 合入主分支。具体步骤见[贡献指南](CONTRIBUTING.md)。

## License

[Apache 2.0](LICENSE)
