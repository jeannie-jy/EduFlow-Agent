# EduFlow-Agent

> **面向计算机科学教育的 AI 教学推演系统**
>
> 输入 CS 知识点，Agent 自主规划教学策略，生成可交互的逐帧推演序列。支持参数调节、教师编辑、质量评审、视频导出。

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0-blue.svg)](https://www.typescriptlang.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Version](https://img.shields.io/badge/version-0.6.0-informational.svg)]()

---

## 当前状态

> **v0.7.0 — 前端重设计 + 安全加固 + 开发体验优化**
>
> 5 个 Agent 协作 + HITL 审批 + DSL 推演 + LLM 优先视频导出的核心链路已跑通，系统可用。
>
> **本次更新 (v0.7.0)：**
> - 🎨 **前端全面重设计**：全新的 Landing 叙事页（产品原理 / 交互案例 / 使用场景 / 模板库）、Dijkstra 公开探索页 (`/explore/dijkstra`)、可中断的交互式 Demo 状态机
> - 🎭 **纸张质感主题系统**：明暗双主题 + 设计 tokens（`--paper`/`--canvas`/`--graph-*`）+ prefers-reduced-motion 适配
> - ♿ **无障碍增强**：焦点管理、ARIA 标注、键盘导航、滚动条隐藏
> - 🔒 **安全加固**：`auth.ts` 全量 try-catch、Content-Security-Policy meta 标签、DeepSeek thinking mode 兼容修复
> - 🧪 **测试覆盖扩展**：130 个前端测试（17 个文件）+ 373 个后端测试
>
> **上一版本 (v0.6.0)：**
> - 🤖 **LLM 驱动 Manim 代码生成**：教学语义 → LLM 自主设计可视化布局/配色/动画，替代纯规则映射
> - ✅ **Manim 脚本质量检测**：6 项静态规则（语法/CJK/lexer/API兼容/转义/调试残留）+ 自动修复 + 失败重试
> - 🎬 **视频导出增强**：双模式渲染（Redis Worker + 进程内 fallback）、FFmpeg 分片合并容错、实时进度轮询
>
> **下一阶段（v0.8+）** 将聚焦于：
> - 🧩 **生成方式可选化**：教学计划审批通过后，可选择需要的产出形式（思维导图 + 知识卡片 / 完整逐帧推演 / 视频导出），按需生成而非全量输出
> - 🎨 **前端美化**：优化 UI/UX 设计，提升视觉表现与交互体验
> - 🔍 **推演功能优化**：修正推演逻辑，实现真正推演功能（目标超越 gemini）
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
- **模块化产出（规划中）**：教学计划生成后，可灵活选择产出组合（思维导图 / 知识卡片 / 逐帧推演 / 视频），按需取用而非全量生成

## 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| **LLM** | DeepSeek-v4-pro (主) | API 调用（兼容 OpenAI 接口），可切换备用模型 |
| **Embedding** | text-embedding-3-small (1536维) | 知识库语义检索，可平替通义千问 text-embedding-v4 |
| **Agent 编排** | LangGraph | 5 节点 StateGraph + HITL interrupt + Postgres Checkpointer |
| **后端** | Python 3.12+ / FastAPI | 异步 REST API + SSE 流式推送 + Alembic 数据库迁移 |
| **前端** | React 18 + TypeScript + Vite 8 | Tailwind CSS 4 + Base UI + 纸张质感主题系统 |
| **数据库** | PostgreSQL 16 + pgvector + Redis 7 | 向量检索 + 任务队列 + 缓存 |
| **存储** | MinIO (S3 兼容) | 上传文件 + 渲染产物 |
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
# Python 3.12 推荐（3.14 部分包无预编译 wheel）
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

## 文档索引

| 文档 | 说明 |
|------|------|
| [需求文档](docs/requirements/自主Agent教学推演系统_需求文档包_v1.md) | 用户故事、用例、功能边界 |
| [设计文档](docs/design/智能教学推演系统设计文档.md) | 完整技术方案（Multi-Agent + DSL + 双路径渲染） |
| [前端设计规范](web/DESIGN.md) | 前端 UI/UX 设计参考 |
| [开发任务与接口规范](docs/开发任务与接口规范.md) | Phase 1-3 任务拆分 + API 契约 + DSL Schema 速查 |
| [术语表](docs/GLOSSARY.md) | 中英术语对照 |
| [贡献指南](CONTRIBUTING.md) | 分支策略与协作规范 |

## 开发

### 运行测试

```bash
# 后端测试（agent/ 目录下）
cd agent
python -m pytest tests/ -v           # 运行全部 373 个测试
python -m pytest tests/ --cov=.      # 带覆盖率报告

# 前端测试（web/ 目录下）
cd web
npm test                             # 运行 Vitest（130 个测试，17 个文件）
npm run typecheck                    # TypeScript 类型检查
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

```bash
cd agent
# 生成迁移脚本
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head
```

---

## License

[Apache 2.0](LICENSE)
