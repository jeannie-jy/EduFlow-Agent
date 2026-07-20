# EduFlow-Agent

> **面向计算机科学教育的 AI 教学推演系统**
>
> 输入 CS 知识点，Agent 自主规划教学策略，生成可交互的逐帧推演序列。支持参数调节、教师编辑、视频导出。

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev/)

---

## 项目简介

EduFlow-Agent 是一个 Multi-Agent 教学推演系统。用户通过自然语言输入 CS 概念（如"Dijkstra 最短路径算法"），系统通过 5 个协作 Agent 自主规划教学步骤、构建知识图谱、生成逐帧 DSL（中间表示），最终在 Web 端呈现可交互的推演动画，并可按需导出为 Manim 教学视频。

**当前阶段：** Phase 2 功能闭环（5 Agent 编排 + 编辑 + 质量评估 + 视频导出），详见[实施计划](docs/实施计划/auto-fix-plan.md)。

## 核心特点

- **Multi-Agent 自主规划**：Planner → Knowledge → Coder → Quality → Reflection 五个 Agent 协作
- **DSL 驱动的双路径渲染**：同一份中间表示驱动 Web 交互推演 + Manim 视频导出
- **逐帧交互式推演**：暂停、回退、调速、参数实时调节，支持交互帧等待用户操作
- **教师编辑器**：逐帧编辑、锁定、局部重生成、版本管理
- **质量保障闭环**：自动 Schema 校验 + 状态一致性检查 + LLM 六维度评分 + 反思修订

## 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| **LLM** | DeepSeek-Chat (主) | API 调用（兼容 OpenAI 接口） |
| **Embedding** | text-embedding-3-small (1536维) | pgvector 向量语义检索 |
| **Agent 编排** | LangGraph | 5 节点 StateGraph + Human-in-the-Loop + Postgres Checkpointer |
| **后端** | Python 3.12+ / FastAPI | 异步 REST API + SSE 流式推送 |
| **前端** | React 18 + TypeScript + Vite | React Flow 图渲染 + Tailwind CSS |
| **数据库** | PostgreSQL 16 + pgvector + Redis 7 | 向量检索 + 任务队列 + 缓存 |
| **存储** | MinIO (S3 兼容) | 上传文件 + 渲染产物 |
| **视频导出** | Manim CE + FFmpeg (Docker) | 确定性 DSL→Manim 脚本转换 |

## 快速开始

### 前置条件

- Docker Desktop 24+
- Node.js 20+ / npm 10+（前端开发）
- Python 3.12+（后端开发，Docker 模式不需要）

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

### 知识库初始化（需要时）

首次运行后，执行 embedding 播种脚本：
```bash
cd agent
python -m scripts.seed_embeddings
```

## 项目结构

```
EduFlow-Agent/
├── agent/                    # Python 后端
│   ├── agents/               # LangGraph Agent 编排（nodes/graph/state/prompts）
│   ├── api/                  # FastAPI 路由（9 个模块）
│   ├── adapters/             # DSL→Manim 确定性转换器
│   ├── db/                   # SQLAlchemy ORM 模型 + 数据库连接
│   ├── plugins/              # 领域插件系统（DomainPlugin 协议 + CS 内置插件）
│   ├── schema/               # Pydantic DSL Schema（14 种 VisualObject + 16 种 Animation）
│   ├── services/             # 生成流程 + 知识库服务
│   ├── tools/                # Tool 实现（DSL 校验 + 参数设计 + 资源生成）
│   ├── workers/              # Manim 渲染 Worker
│   ├── scripts/              # 知识库 embedding 播种脚本
│   └── tests/                # 373 个单元/集成测试
├── web/                      # React 前端
│   ├── src/
│   │   ├── app/              # 路由 + Provider
│   │   ├── components/       # UI 组件 + Workbench + visual-objects
│   │   ├── features/         # Auth + Landing
│   │   ├── pages/            # 11 个页面路由
│   │   ├── services/         # API 客户端 + SSE 连接 + 8 个服务模块
│   │   └── theme/            # 深色/浅色主题
│   └── package.json
├── db/                       # PostgreSQL 初始化 SQL
├── docs/                     # 设计文档 + 需求文档 + 开发规范 + 实施计划
├── docker-compose.yml        # 5 服务编排
├── .env.example              # 环境变量模板
├── start.ps1                 # Windows 一键启动脚本
├── start.sh                  # Linux/macOS 一键启动脚本
└── DEPLOY.md                 # 部署指南
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

## 团队与分工

| 角色 | 负责人 | 职责 |
|------|--------|------|
| **架构** | 仲嘉辉 | 系统架构设计、技术选型、Multi-Agent 方案 |
| **需求** | 屠育玮 | 需求分析、用户故事、市场调研 |
| **前端** | 崔杰 | Web 交互界面、可视化渲染、动画系统 |
| **后端** | 王婧瑜 | FastAPI、Agent 实现、API 服务、数据库 |

## License

[Apache 2.0](LICENSE)
