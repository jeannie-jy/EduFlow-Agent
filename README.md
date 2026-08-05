# EduFlow-Agent

> **面向计算机科学教育的 AI 教学推演系统**
>
> 输入 CS 知识点，Agent 自主规划教学策略，生成可交互的逐帧推演序列。支持参数调节、教师编辑、质量评审、视频导出。

<p align="center">
  <img src="docs/宣传页.png" alt="EduFlow 宣传页" width="800" />
</p>

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0-blue.svg)](https://www.typescriptlang.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Version](https://img.shields.io/badge/version-0.8.0-informational.svg)]()

---

## 当前状态

> **v0.8.0 — 模块化生成主线 + 可靠性加固**
>
> 5 个 Agent 协作 + HITL 审批 + DSL 推演 + 单轨视频导出的核心链路已跑通，系统可用。

**本次更新 (v0.8.0)：**
- 🧩 **生成方式可选化**：10 种模块生成器（思维导图/知识卡片/推演脚本/小练习/教学视频/算法对比/常见误区/学习路径/代码沙箱/交互推演），按需勾选生成
- 🎨 **UI 流程重塑**：步骤指示器（select → plan → results）替代 Tab 栏，新建流程统一收拢到 ProjectWorkspace
- 🛡️ **数据库初始化落地**：Alembic 基线迁移（8 张业务表 + knowledge_base），agent-api 启动时自动 `alembic upgrade head`，不再依赖 init.sql 建表
- 🔧 **前端类型门禁**：`npm run typecheck` 改为 `tsc -b`（此前对 solution tsconfig 是空操作），34 个存量 TS 错误清零；修复 SSE 模块事件回调解构缺失（模块进度此前被静默丢弃）
- 🎬 **视频导出单轨化**：废弃从未跑通的独立 manim-worker 容器，统一走 API 进程内渲染；修复导出失败时 DB 状态同步顺序
- 🧪 **测试覆盖扩展**：694 个后端测试 + 224 个前端测试全绿（含新增的生成器可靠性/冒烟测试）

**历史版本：**
- **v0.7.0 — 前端重设计 + 安全加固**：Landing 叙事页、Dijkstra 公开探索页、纸张质感主题系统、无障碍增强、130 个前端测试 + 373 个后端测试
- **v0.6.0 — LLM 驱动 Manim**：教学语义 → LLM 自主设计可视化布局/配色/动画、Manim 脚本 6 项静态质量检测 + 自动修复 + 失败重试、双模式渲染雏形

**下一阶段规划：**
- 🔐 **真实后端认证**：当前为前端占位登录（见「已知局限」），计划 HttpOnly cookie 会话 + `/api/auth/me`
- 🚀 **并发视频导出**：当前单轨导出并发上限 2（见「已知局限」），计划引入 Celery/RQ 任务队列或重建独立渲染 Worker
- 🎓 **模板库扩充**：更多公开教学案例与按知识点预置的生成模板

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
- **模块化产出（规划中）**：教学计划生成后，可灵活选择产出组合（思维导图 / 知识卡片 / 逐帧推演 / 视频），按需取用而非全量生成

## 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| **LLM** | DeepSeek (主) | API 调用（兼容 OpenAI 接口），`LLM_MODEL` 可切换（默认 `deepseek-chat`） |
| **Embedding** | text-embedding-3-small (1536维) | 知识库语义检索，可平替通义千问 text-embedding-v4 |
| **Agent 编排** | LangGraph | 5 节点 StateGraph + HITL interrupt + Postgres Checkpointer |
| **后端** | Python 3.12+ / FastAPI | 异步 REST API + SSE 流式推送 + Alembic 数据库迁移 |
| **前端** | React 18 + TypeScript + Vite 8 | Tailwind CSS 4 + Base UI + 纸张质感主题系统 |
| **数据库** | PostgreSQL 16 + pgvector + Redis 7 | 向量检索 + 任务队列 + 缓存 |
| **存储** | 本地磁盘 (MinIO 预留) | 上传文件 + 渲染产物存本地 `data/`；MinIO 服务已就绪但 S3 客户端未接入 |
| **视频导出** | Manim CE + FFmpeg | LLM 驱动代码生成（默认） + 确定性规则回退 + Validator 质量检测 |

## 快速开始

### 前置条件

- Docker Desktop 24+
- Node.js 20+ / npm 10+（前端开发）
- Python 3.12+（后端开发，Docker 模式不需要）
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

服务列表（4 个容器）：

| 服务 | 端口 | 说明 |
|------|------|------|
| `agent-api` | 8000 | FastAPI 后端 API（启动时自动执行数据库迁移） |
| `postgres` | 5432 | PostgreSQL 16 + pgvector |
| `redis` | 6379 | Redis 7 缓存 + 导出状态追踪 |
| `minio` | 9000/9001 | S3 兼容对象存储（预留，后端尚未接入） |

验证：
```bash
curl http://localhost:8000/api/health
# → {"status":"ok","version":"0.8.0"}
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
# Python 3.12 推荐（3.14 部分包无预编译 wheel）
# Windows 用户注意：pycairo 可能需要手动下载 wheel
# 下载地址: https://github.com/cgohlke/pycairo-build/releases
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 --reload-dir agents --reload-dir api --reload-dir adapters --reload-dir db --reload-dir generators --reload-dir plugins --reload-dir schema --reload-dir services --reload-dir tools --reload-dir alembic --reload-dir scripts --reload-dir main.py

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

## 已知局限与后续可拓展思路

- **认证为前端占位实现**：当前用 `simulateAuth()` + localStorage 模拟登录（无后端 `/api/auth/*` 端点），**不可用于安全决策**。后续计划：HttpOnly cookie 会话 + `GET /api/auth/me` 验证、密码哈希与限流在后端完成。
- **视频导出并发上限为 2**：导出在 API 进程内的线程池（`ThreadPoolExecutor(max_workers=2)`）执行，第 3 个导出任务需排队。历史上有独立的 `manim-worker` 容器，但因镜像缺依赖、未传 LLM API Key、Manim 版本分裂（0.18 vs 0.20）从未跑通，v0.8.0 已废弃，导出统一走进程内单轨。若并发导出成为硬需求，推荐引入 Celery/RQ 任务队列，或重建独立渲染 Worker（镜像体积、Manim 依赖隔离、队列消费、横向扩展）。
- **参数 recompute 触发完整重新生成**：`api/parameters.py` 更新参数后的 recompute 目前复用完整生成流，而非范围重算（`recompute_scope: local` 语义尚未实现）。
- **MinIO 尚未接入**：docker-compose 提供 minio 服务，但后端暂无 S3 客户端；上传文件与导出产物存储于本地磁盘（`data/uploads` / `data/exports`）。接入后需迁移存储层并处理存量数据。
- **模块失败保留在结果页**：模块生成失败会以 `module_errors` 落库并标记项目 `failed`，但暂未提供"失败模块一键重试"的 UI 入口（可单模块重生成）。

## 文档索引

| 文档 | 说明 |
|------|------|
| [需求文档](docs/requirements/自主Agent教学推演系统_需求文档包_v1.md) | 用户故事、用例、功能边界 |
| [设计文档](docs/design/智能教学推演系统设计文档.md) | 完整技术方案（Multi-Agent + DSL + 双路径渲染） |
| [设计系统与前端规范](DESIGN.md) | 视觉/交互/实现指南（学术纸本 × 互动技术手稿） |
| [开发任务与接口规范](docs/开发任务与接口规范.md) | Phase 1-3 任务拆分 + API 契约 + DSL Schema 速查 |
| [术语表](docs/GLOSSARY.md) | 中英术语对照 |
| [贡献指南](CONTRIBUTING.md) | 分支策略与协作规范 |

## 开发

### 运行测试

```bash
# 后端测试（agent/ 目录下）
cd agent
python -m pytest tests/ -v           # 运行全部 694 个测试
python -m pytest tests/ --cov=.      # 带覆盖率报告

# 前端测试（web/ 目录下）
cd web
npm test                             # 运行 Vitest（224 个测试，25 个文件）
npm run typecheck                    # TypeScript 类型检查（tsc -b，真实门禁）
npm run verify                       # 完整验证（类型 + 测试 + 构建）
	npm run build                        # 生产构建
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
| `FFMPEG_PATH` | FFmpeg 安装目录（留空自动查找） | (空) |
| `AGENT_LOG_LEVEL` | Agent 日志级别 | `INFO` |

### 数据库迁移

业务表由 Alembic 管理（基线迁移 `agent/alembic/versions/0001_baseline.py`：8 张 ORM 表 + knowledge_base），
Docker 部署时 `agent-api` 启动前会自动执行 `alembic upgrade head`；手动部署需先执行一次：

```bash
cd agent
# 执行迁移（首次部署必须；已存在的旧库无保留价值，请 docker compose down -v 后重建）
alembic upgrade head

# 生成新迁移脚本（修改 db/models.py 后）
alembic revision --autogenerate -m "description"
```

---

## License

[Apache 2.0](LICENSE)
