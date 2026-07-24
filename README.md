# EduFlow-Agent

> **面向计算机科学教育的 AI 教学推演系统**
>
> 输入 CS 知识点，Agent 自主规划教学策略，生成可交互的逐帧推演序列。支持参数调节、教师编辑、质量评审、视频导出。

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0-blue.svg)](https://www.typescriptlang.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Version](https://img.shields.io/badge/version-0.5.0-informational.svg)]()

---

## 当前状态

> **v0.5.0 — 基本功能闭环**
>
> 5 个 Agent 协作 + HITL 审批 + DSL 推演 + 视频导出的核心链路已跑通，系统可用。
>
> **下一阶段（v0.6+）** 将聚焦于：
> - 🎨 **前端美化**：优化 UI/UX 设计，提升视觉表现与交互体验
> - 🎬 **视频导出增强**：完善 Manim 视频导出功能、实现更稳定的渲染管线
> - 🔍 **推演功能优化**：修正推演逻辑，实现真正推演功能（目标超越gemini）
> - ⚡ **流程优化**：缩短生成耗时、改进中断恢复体验

---

## 项目简介

EduFlow-Agent 是一个 Multi-Agent 教学推演系统。用户通过自然语言输入 CS 概念（如"Dijkstra 最短路径算法"），系统通过 5 个协作 Agent 自主规划教学步骤、构建知识图谱、生成逐帧 DSL（中间表示），经 Human-in-the-Loop 审批后在 Web 端呈现可交互的推演动画，并可按需导出为 Manim 教学视频。

## 核心特点

- **Multi-Agent 自主规划**：Planner → Knowledge → Coder → Quality → Reflection 五个 Agent 协作，自动生成教学计划与逐帧推演
- **Human-in-the-Loop 审批**：Planner 输出后中断等待教师确认/拒绝教学计划，支持从中断点恢复生成
- **DSL 驱动的双路径渲染**：同一份中间表示（DSL）驱动 Web 交互推演 + Manim 视频导出
- **逐帧交互式推演**：React Flow 图渲染，支持暂停、回退、调速、参数实时调节
- **教师工作台**：逐帧编辑、锁定、局部重生成、版本管理、反馈收集
- **质量保障闭环**：自动 Schema 校验 + 状态一致性检查 + LLM 六维度评分 + Reflection 反思修订循环
- **多模态素材解析**：支持 PDF / PPT / Markdown / 代码文件上传，自动提取内容辅助教学

## 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| **LLM** | DeepSeek-Chat (主) | API 调用（兼容 OpenAI 接口），可切换备用模型 |
| **Embedding** | text-embedding-3-small (1536维) | 知识库语义检索，可平替通义千问 text-embedding-v4 |
| **Agent 编排** | LangGraph | 5 节点 StateGraph + HITL interrupt + Postgres Checkpointer |
| **后端** | Python 3.11+ / FastAPI | 异步 REST API + SSE 流式推送 + Alembic 数据库迁移 |
| **前端** | React 18 + TypeScript + Vite 8 | React Flow 图渲染 + Tailwind CSS 4 + Base UI |
| **数据库** | PostgreSQL 16 + pgvector + Redis 7 | 向量检索 + 任务队列 + 缓存 |
| **存储** | MinIO (S3 兼容) | 上传文件 + 渲染产物 |
| **视频导出** | Manim CE + FFmpeg (Docker) | 确定性 DSL → Manim 脚本转换，Redis Worker 异步渲染 |

## 快速开始

### 前置条件

- Docker Desktop 24+
- Node.js 20+ / npm 10+（前端开发）
- Python 3.11+（后端开发，Docker 模式不需要）
- FFmpeg（视频导出依赖，Docker 模式不需要）
  - Windows: `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `apt install ffmpeg`

### 方式一：一键启动脚本

**Windows PowerShell：**
```powershell
# 1. 配置环境变量
copy .env.example .env
# 编辑 .env，填入 LLM_API_KEY（DeepSeek）和 EMBEDDING_API_KEY（OpenAI）

# 2. 一键启动全部服务
.\start.ps1
```

**Linux / macOS / Git Bash：**
```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key

# 2. 一键启动
chmod +x start.sh
./start.sh
```

也可以按模块启动：
```bash
./start.sh infra     # 仅启动 Docker 基础设施
./start.sh backend   # 仅启动 FastAPI 后端
./start.sh frontend  # 仅启动 Vite 前端
```

### 方式二：Docker Compose（全容器化）

```bash
cp .env.example .env
# 编辑 .env 填入 API Key
docker compose up -d
```

服务列表（5 个容器）：

| 服务 | 端口 | 说明 |
|------|------|------|
| `agent-api` | 8000 | FastAPI 后端 API |
| `postgres` | 5432 | PostgreSQL 16 + pgvector |
| `redis` | 6379 | Redis 7 缓存 + 任务队列 |
| `manim-worker` | - | Manim 渲染 Worker |
| `minio` | 9000/9001 | S3 兼容对象存储 |

验证：
```bash
curl http://localhost:8000/api/health
# → {"status":"ok","version":"0.1.0"}
```

### 方式三：手动启动（开发模式）

```bash
# 1. 环境变量
cp .env.example .env

# 2. 基础设施
docker compose up -d postgres redis minio

# 3. 后端（终端 1）
cd agent
pip install -r requirements.txt
# Windows 用户注意：pycairo 可能需要手动下载 wheel
# 下载地址: https://github.com/cgohlke/pycairo-build/releases
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 4. 前端（终端 2）
cd web
npm install
npm run dev
```

打开浏览器访问：
- **前端**: http://localhost:5173
- **后端 API 文档**: http://localhost:8000/docs
- **MinIO 控制台**: http://localhost:9001

### 知识库初始化（可选）

首次运行后，执行 embedding 播种脚本初始化 CS 术语向量库：
```bash
cd agent
python -m scripts.seed_embeddings
```

## 项目结构

```
EduFlow-Agent/
├── agent/                          # Python 后端
│   ├── adapters/                   # DSL → Manim 确定性转换器
│   │   └── manim_adapter.py
│   ├── agents/                     # LangGraph Agent 编排
│   │   ├── state.py                # AgentState 类型定义
│   │   ├── graph.py                # 5 节点 StateGraph 构建 + checkpointer 管理
│   │   ├── nodes.py                # 5 个 Agent 节点实现（planner/knowledge/coder/quality/reflection）
│   │   ├── prompts.py              # LLM Prompt 模板
│   │   └── llm_client.py           # LLM / Embedding 客户端封装
│   ├── alembic/                    # 数据库迁移（Alembic）
│   ├── api/                        # FastAPI 路由（9 个模块 + 中间件）
│   │   ├── router.py               # 路由聚合入口
│   │   ├── projects.py             # 项目 CRUD
│   │   ├── generate.py             # 生成流程 + SSE 流式端点
│   │   ├── frames.py               # 帧编辑与锁定
│   │   ├── parameters.py           # 参数管理与调节
│   │   ├── knowledge.py            # 知识库检索
│   │   ├── feedback.py             # 教师反馈收集
│   │   ├── export.py               # 视频导出控制
│   │   ├── materials.py            # 素材上传与解析
│   │   ├── versions.py             # 项目版本管理
│   │   ├── deps.py                 # 依赖注入（数据库会话、Project ID 解析）
│   │   ├── middleware.py           # 请求日志与 request_id 追踪
│   │   └── error_handlers.py       # 全局异常处理
│   ├── db/                         # SQLAlchemy ORM
│   │   ├── database.py             # 异步数据库引擎与会话工厂
│   │   └── models.py               # 9 个 ORM 模型（Project/Frame/Parameter/Feedback/…）
│   ├── plugins/                    # 领域插件系统
│   │   ├── domain_plugin.py        # DomainPlugin 抽象协议
│   │   └── cs_plugin.py            # CS 领域内置插件
│   ├── schema/                     # Pydantic 数据模型
│   │   ├── dsl.py                  # DSL Schema（VisualObject + Animation 等类型）
│   │   └── project.py              # 项目 API Schema
│   ├── services/                   # 业务服务层
│   │   ├── generate_service.py     # 生成流程编排（流式 SSE + 同步 + HITL 恢复 + 局部重生成）
│   │   ├── knowledge_service.py    # 知识库检索服务
│   │   └── project_persistence.py  # DSL 快照与帧表持久化
│   ├── tools/                      # Agent Tool 实现
│   │   ├── validate_dsl.py         # DSL 校验工具
│   │   ├── design_parameters.py    # 参数设计工具
│   │   └── generate_asset.py       # 资源生成工具
│   ├── workers/                    # 异步 Worker
│   │   └── render_worker.py        # Manim 渲染 Worker（Redis 驱动）
│   ├── scripts/                    # 运维脚本
│   │   └── seed_embeddings.py      # 知识库 embedding 播种
│   ├── tests/                      # 测试（376 个单元 / 集成测试，15 个文件）
│   │   ├── conftest.py             # Mock LLM/Embedding 客户端 + 测试数据工厂
│   │   ├── test_agent_nodes.py     # Agent 节点 + 图拓扑测试
│   │   ├── test_generate_service.py # 生成流程 + SSE + HITL 测试
│   │   ├── test_db_integration.py  # 数据库 CRUD + 约束 + 事务测试
│   │   ├── test_api_integration.py # API 集成测试
│   │   ├── test_schema.py          # DSL Schema 测试
│   │   ├── test_schema_edge_cases.py # Schema 边界条件测试
│   │   ├── test_phase2_*.py        # Phase 2 模块测试
│   │   ├── test_phase3.py          # Phase 3 API 测试
│   │   ├── test_prompt_injection.py # Prompt 注入防护测试
│   │   └── test_llm_client.py      # LLM 客户端测试
│   ├── main.py                     # FastAPI 应用入口 + 生命周期
│   ├── config.py                   # 配置管理（pydantic-settings）
│   ├── requirements.txt            # Python 依赖
│   └── Dockerfile                  # Agent API 镜像
├── web/                            # React 前端
│   ├── src/
│   │   ├── app/                    # 路由配置 + Provider
│   │   ├── components/
│   │   │   ├── brand/              # 品牌/图标组件
│   │   │   ├── effects/            # 动效组件
│   │   │   ├── layout/             # 布局组件（导航、页眉等）
│   │   │   ├── ui/                 # 通用 UI 组件（Base UI 封装）
│   │   │   └── workbench/          # 教学推演工作台核心组件
│   │   │       ├── AiStatusStrip.tsx       # Agent 状态指示条
│   │   │       ├── KnowledgeCard.tsx       # 知识图谱卡片
│   │   │       ├── MindmapView.tsx         # 思维导图视图
│   │   │       ├── PlanSequence.tsx        # 教学计划序列
│   │   │       ├── SimulationGraph.tsx     # 帧推演 React Flow 图
│   │   │       ├── SimulationPreview.tsx   # 推演预览
│   │   │       ├── TeachingBrief.tsx       # 教学概览
│   │   │       ├── simulation-model.ts     # 推演模型（状态机）
│   │   │       └── visual-objects/         # 可视化对象渲染
│   │   ├── features/
│   │   │   ├── auth/               # 认证模块
│   │   │   └── landing/            # 首页模块
│   │   ├── hooks/                  # 自定义 React Hooks
│   │   ├── lib/                    # 工具函数库
│   │   ├── pages/                  # 页面组件（6 个路由页面）
│   │   │   ├── Dashboard.tsx       # 项目仪表盘
│   │   │   ├── NewProject.tsx      # 新建项目
│   │   │   ├── ProjectWorkspace.tsx # 项目工作台（核心页面）
│   │   │   ├── TemplateBrowser.tsx # 模板浏览器
│   │   │   └── NotFound.tsx        # 404 页面
│   │   ├── services/               # API 客户端层（10 个模块）
│   │   │   ├── api-client.ts       # HTTP 客户端（拦截器、错误处理）
│   │   │   ├── sse.ts              # SSE 连接管理
│   │   │   ├── projects.ts         # 项目 API
│   │   │   ├── generate.ts         # 生成流程 API
│   │   │   ├── frames.ts           # 帧管理 API
│   │   │   ├── parameters.ts       # 参数 API
│   │   │   ├── knowledge.ts        # 知识库 API
│   │   │   ├── export.ts           # 导出 API
│   │   │   └── versions.ts         # 版本 API
│   │   ├── styles/                 # 全局样式
│   │   ├── test/                   # 前端测试（Vitest + MSW）
│   │   │   └── mocks/              # MSW Mock Handlers
│   │   └── theme/                  # 深色/浅色主题配置
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── db/                            # 数据库初始化
│   └── init.sql                   # PostgreSQL 建表 SQL
├── docs/                          # 文档
│   ├── design/                    # 设计文档
│   │   └── 智能教学推演系统设计文档.md
│   ├── requirements/              # 需求文档
│   │   └── 自主Agent教学推演系统_需求文档包_v1.md
│   ├── 开发任务与接口规范.md        # 开发任务 + API 契约 + DSL Schema 速查
│   └── GLOSSARY.md                # 中英术语对照
├── docker-compose.yml             # 5 服务 Docker Compose 编排
├── .env.example                   # 环境变量模板
├── start.ps1                      # Windows 一键启动脚本
├── start.sh                       # Linux/macOS 一键启动脚本
├── DEPLOY.md                      # 部署指南
├── CONTRIBUTING.md                # 贡献指南
└── LICENSE                        # Apache 2.0
```

## 文档索引

| 文档 | 说明 |
|------|------|
| [需求文档](docs/requirements/自主Agent教学推演系统_需求文档包_v1.md) | 用户故事、用例、功能边界 |
| [设计文档](docs/design/智能教学推演系统设计文档.md) | 完整技术方案（Multi-Agent + DSL + 双路径渲染） |
| [开发任务与接口规范](docs/开发任务与接口规范.md) | Phase 1-3 任务拆分 + API 契约 + DSL Schema 速查 |
| [部署指南](DEPLOY.md) | Docker Compose 部署 + 环境变量 + 故障排查 |
| [术语表](docs/GLOSSARY.md) | 中英术语对照 |
| [贡献指南](CONTRIBUTING.md) | 分支策略与协作规范 |

## 开发

### 运行测试

```bash
# 后端测试（agent/ 目录下）
cd agent
python -m pytest tests/ -v           # 运行全部 376 个测试
python -m pytest tests/ --cov=.      # 带覆盖率报告

# 前端测试（web/ 目录下）
cd web
npm test                             # 运行 Vitest 测试套件
npm run typecheck                    # TypeScript 类型检查
npm run verify                       # 完整验证（类型 + 测试 + 构建）
```

### 环境变量

核心环境变量（详见 `.env.example`）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | DeepSeek API Key | - |
| `LLM_MODEL` | LLM 模型名称 | `deepseek-chat` |
| `EMBEDDING_API_KEY` | Embedding API Key | - |
| `DATABASE_URL` | 数据库连接字符串 | `postgresql+asyncpg://agent:changeme@localhost:5432/eduflow` |
| `REDIS_URL` | Redis 连接字符串 | `redis://localhost:6379` |
| `AGENT_LOG_LEVEL` | Agent 日志级别 | `INFO` |

### 数据库迁移

```bash
cd agent
# 生成迁移脚本
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head
```

---

## 团队与分工

| 角色 | 负责人 | 职责 |
|------|--------|------|
| **架构** | 仲嘉辉 | 系统架构设计、技术选型、Multi-Agent 方案 |
| **需求** | 屠育玮 | 需求分析、用户故事、市场调研 |
| **前端** | 崔杰 | Web 交互界面、可视化渲染、动画系统 |
| **后端** | 王婧瑜 | FastAPI、Agent 实现、API 服务、数据库 |

## License

[Apache 2.0](LICENSE)
