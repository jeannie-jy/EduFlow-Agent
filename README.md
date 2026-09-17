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
[![Version](https://img.shields.io/badge/version-1.0.0-informational.svg)]()

---

## 当前状态

> **v1.0.0 — 发布前质量与安全验收**
>
> 前后端回归、真实视频渲染、安全边界、故障恢复、对象存储迁移与公开部署保护门禁已完成工程化验收；真实在线模型质量评测仍需显式凭据与成本授权。
**本次更新 (v1.0.0)：**
- **前端回归修复**：补齐新建项目页模块目录的 MSW 接口模拟，`npm run verify` 全绿（42 个测试文件 / 302 项测试）。
- **后端质量基线**：常规非在线、非渲染回归通过 `1174 passed，1 skipped，6 deselected`。
- **真实视频验收**：Manim/FFmpeg golden smoke、确定性布局审计（重叠/越界/文本截断）、双 Worker 并行与 Redis/PostgreSQL/MinIO 故障恢复验证通过。
- **渲染安全加固**：无网络/无凭据 Sandbox、脚本摘要校验、路径与 symlink 越界拒绝、超时/OOM/工作区配额、恶意脚本、容器中断重启及孤儿 claim 回收验证通过。
- **公开部署保护**：公开视频默认关闭；生产环境未完成任务级隔离与安全审批时 fail-closed。
- **迁移可靠性**：本地 PostgreSQL/MinIO 历史数据迁移演练通过；补充部分上传失败时的对象补偿机制。
- **发布验收边界**：真实 Tool Calling Bench、50 案例独立 Judge、至少 20% 人工校准尚未运行；本版本不宣称真实模型质量、成功率或成本。

**历史版本：**
- **v0.8.0 — 模块化生成主线 + 可靠性加固**：10 种模块化教学产物、任务化视频导出、真实后端会话、素材治理、成果版本追踪与关键操作审计
- **v0.7.0 — 前端重设计 + 安全加固**：Landing 叙事页、Dijkstra 公开探索页、纸张质感主题系统、无障碍增强、130 个前端测试 + 373 个后端测试
- **v0.6.0 — LLM 驱动 Manim**：教学语义 → LLM 自主设计可视化布局/配色/动画、Manim 脚本 6 项静态质量检测 + 自动修复 + 失败重试、双模式渲染雏形

**下一阶段规划：**
- **成果工作台深化**：在现有逐帧编辑和版本管理基础上，继续推进帧批量编辑、成果校验视图与发布流程
- **时效优化**：推进 LLM 调用并行化、SSE 进度细化、模块并发调优，以及更细粒度的前端代码分割和沙箱运行时懒加载
- **视频任务横向扩展**：在现有 PostgreSQL lease Worker 基础上完善多 Worker 容量验证、队列优先级与每任务临时渲染容器
- **模板库扩充**：更多公开教学案例与按知识点预置的生成模板
- **导出视频优化**：已接入确定性布局审计，将元素重叠、画面越界和文本截断写入渲染配置；已完成真实 Manim/FFmpeg 样本验收，后续继续修复高频布局问题

---

## 项目简介

EduFlow-Agent 是一个有状态 Agent 教学推演系统。用户通过自然语言输入 CS 概念（如“Dijkstra 最短路径算法”），系统通过统一 LangGraph 中的 5 个功能节点规划教学步骤、构建知识图谱、生成逐帧 DSL（中间表示），经 Human-in-the-Loop 审批后在 Web 端呈现可交互的推演动画，并可按需导出为 Manim 教学视频。

## 核心特点

- **统一 Agent 工作流**：Planner → Knowledge → Coder → Quality → Reflection 五个功能节点共享状态并形成生成、校验与修订闭环
- **Human-in-the-Loop 审批**：Planner 输出后中断等待教师确认/拒绝教学计划，支持从中断点恢复生成
- **DSL 驱动的双路径渲染**：同一份中间表示（DSL）驱动 Web 交互推演 + Manim 视频导出
- **逐帧交互式推演**：支持暂停、回退、调速，以及参数影响预览与受控重算
- **教师工作台**：逐帧编辑、锁定、局部重生成、版本管理、反馈收集
- **质量保障闭环**：自动 Schema 校验 + 状态一致性检查 + LLM 六维度评分 + Reflection 反思修订循环
- **多模态素材解析**：支持 PDF / PPT / Markdown / 代码文件上传，自动提取内容辅助教学
- **模块化产出**：教学计划生成后按需勾选成果模块（思维导图 / 知识卡片 / 交互推演 / 对比分析 / 教学视频等），逐帧推演脚本作为基础成果自动生成

## 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| **LLM** | DeepSeek（主）/阿里百炼（Qwen） | 生产通过服务端 KMS BYOK 调用固定官方端点；默认 DeepSeek `deepseek-chat` |
| **Embedding** | 阿里百炼 `text-embedding-v4`（1024维） | 生产 BYOK 语义检索；未配置时明确降级为关键词检索 |
| **Agent 编排** | LangGraph | 5 节点 StateGraph + HITL interrupt + Postgres Checkpointer |
| **后端** | Python 3.12+ / FastAPI | 异步 REST API + SSE 流式推送 + Alembic 数据库迁移 |
| **前端** | React 18 + TypeScript + Vite 8 | Tailwind CSS 4 + Base UI + 纸张质感主题系统 |
| **数据库** | PostgreSQL 16 + pgvector + Redis 7 | 向量检索 + 任务队列 + 缓存 |
| **存储** | ArtifactStore（MinIO / 本地） | Compose 将导出产物和上传素材写入 MinIO；本地后端用于开发与测试 |
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

### 方式一：混合开发模式（推荐）

此模式在 Docker 中运行 PostgreSQL、Redis 和 MinIO，在宿主机上以热更新方式运行
FastAPI 与 Vite。启动脚本会等待 PostgreSQL 就绪，并在启动后端前自动检查/升级数据库迁移。

**Windows PowerShell：**

```powershell
# 首次使用：配置环境变量并创建 Python 3.12 虚拟环境
Copy-Item .env.example .env
py -3.12 -m venv agent/.venv
# 编辑 .env：替换数据库/MinIO 凭证；全局模型 Key 仅用于本地开发

# 启动基础设施、后端和前端（不传参等价于 -All）
.\start.ps1
```

**Linux / macOS / Git Bash：**

```bash
# 首次使用：配置环境变量并创建 Python 3.12 虚拟环境
cp .env.example .env
python3.12 -m venv agent/.venv
# 编辑 .env，替换数据库/MinIO 凭证；公开部署使用 KMS BYOK

chmod +x start.sh
./start.sh
```

也可按模块启动。`Backend` 模式要求 PostgreSQL/Redis 已运行，`Frontend` 模式要求后端已运行：

```powershell
# Windows PowerShell
.\start.ps1 -Infra
.\start.ps1 -Backend
.\start.ps1 -Frontend
.\start.ps1 -Video       # 基础设施 + 视频 Worker/沙箱 + queue 模式后端
.\start.ps1 -All -Video  # 完整开发栈并启用视频制作
.\start.ps1 -All
```

```bash
# Linux / macOS / Git Bash
./start.sh infra
./start.sh backend
./start.sh frontend
./start.sh video
./start.sh all-video
./start.sh all
```

常规 `-All` / `all` 保持视频执行关闭，避免开发 API 意外执行生成代码；需要联调视频时，
使用 `-Video` / `video`。脚本会启动 `render-worker` 与无网络 `render-sandbox`，并仅对
新启动的本地 API 设置 `MANIM_EXECUTION_MODE=queue` 和 MinIO 产物存储。若 8000 端口
已有旧后端，请先在原后端终端按 `Ctrl+C`，再运行视频模式。

### 方式二：Docker Compose（完整应用容器化）

```powershell
Copy-Item .env.example .env
# 编辑 .env：必须替换 DB_PASSWORD、MINIO_USER 和 MINIO_PASSWORD；模型 Key 由用户在前端绑定
docker compose up -d --build
```

Linux / macOS 将第一行换为：

```bash
cp .env.example .env
```

启动后访问 `http://localhost:5173`。Web 通过同源 `/api` 反向代理后端。

默认启动 7 个容器；`video` profile 增加 2 个视频服务，`observability` profile
增加 Prometheus 和 Grafana：

| 服务 | 端口 | 说明 |
|------|------|------|
| `web` | 5173 | Nginx 托管的前端生产构建与 API 反向代理 |
| `migrate` | 无 | 一次性 Alembic 发布 Job |
| `agent-api` | 8000 | FastAPI 后端 API（等待迁移 Job 成功后启动） |
| `postgres` | 5432 | PostgreSQL 16 + pgvector |
| `redis` | 6379 | Redis 7 缓存 + 导出状态追踪 |
| `minio` | 9000/9001 | S3 兼容对象存储（持久化导出产物与上传素材） |
| `task-worker` | 无 | 持久化反馈 Reflection 与材料解析准备器 |
| `material-sandbox` | 无 | 无网络、无服务凭据的 PDF/PPTX/文本解析器 |
| `render-worker` | 无 | 有凭据的任务领取与 Manim 脚本准备器（`video` profile） |
| `render-sandbox` | 无 | 无网络、无服务凭据的 Manim 执行器（`video` profile） |

安全默认值：容器环境的 `MANIM_EXECUTION_MODE` 默认为 `disabled`，因此不会在
API 进程执行模型生成的 Python。需要视频导出时，显式设置 API 为排队模式并启用
独立 Worker：

```powershell
# Windows PowerShell
$env:MANIM_EXECUTION_MODE = "queue"
docker compose --profile video up -d --build
Remove-Item Env:MANIM_EXECUTION_MODE
```

```bash
# Linux / macOS / Git Bash
MANIM_EXECUTION_MODE=queue docker compose --profile video up -d --build
```

也可将 `MANIM_EXECUTION_MODE=queue` 写入 `.env`，再直接启动 profile。可观测与组合模式：

```powershell
docker compose --profile observability up -d
docker compose --profile video --profile observability up -d --build
```

准备器使用数据库 lease 保证任务可恢复，并把已校验脚本的 SHA-256 随请求写入共享任务目录；
`network_mode: none` 的无凭证沙箱在执行前复核摘要，拒绝审批后篡改。两个容器均使用非 root 用户、只读根文件系统、
能力移除及 CPU/内存/PID 限制。Worker 对失败 attempt 执行带 jitter 的指数退避；
沙箱运行期间还会检查每任务目录的总字节和文件数，超限或超时都会回收整个渲染进程组。
当前仍是常驻沙箱而非每任务临时容器，更完整的恶意样本与压力验证仍属后续加固项。
公开账户的视频导出默认关闭；生产环境即使显式打开，也必须先完成每任务隔离并设置
`VIDEO_PUBLIC_ISOLATION_APPROVED=true`，否则普通用户请求会被拒绝。

视频脚本默认使用 `MANIM_SCRIPT_MODE=deterministic`，直接把已校验的逐帧 DSL 编译为
Manim，不增加模型调用。需要实验更自由的视觉编排时可设为 `llm`；LLM 调用或脚本渲染
失败会在同一任务内自动降级到确定性编译，不再通过整任务重试重复消耗模型 Token。

Compose 不再为数据库和 MinIO 提供隐式默认口令，启动前必须在 `.env` 设置
`DB_PASSWORD`、`MINIO_USER`、`MINIO_PASSWORD`。数据库、Redis、API 与 MinIO 端口
默认只绑定回环地址，仅 Web 入口对外监听；后端镜像采用构建/运行双阶段并移除编译工具链。

验证（PowerShell 可将 `curl` 替换为 `Invoke-RestMethod -Uri`）：

```bash
curl http://localhost:8000/api/health
# → {"status":"ok","version":"0.9.0"}
curl http://localhost:8000/api/ready
# → PostgreSQL、Redis、ArtifactStore 均可用时返回 {"status":"ready",...}
```

日常停止使用 `docker compose down`，数据卷会被保留。`docker compose down -v`
会删除 PostgreSQL、Redis 和 MinIO 数据，仅在明确需要重置本地环境时使用。

专用测试环境可运行
`python agent/scripts/compose_fault_smoke.py --services redis postgres minio`
做真实依赖停服/恢复验收；仓库也提供手动 `Compose Fault Injection` CI 工作流。
该脚本不触发付费模型调用，真实模型 Tool Calling 仍通过显式授权的 EduFlowBench
online runner 验证。

### 方式三：手动启动（分终端调试）

以下命令均从仓库根目录开始执行。本地后端默认使用文件型
`ArtifactStore`，因此常规开发只需启动 PostgreSQL 和 Redis：

```powershell
# Windows PowerShell：环境变量与基础设施
Copy-Item .env.example .env
docker compose up -d postgres redis

# 终端 1：后端
cd agent
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock.txt
python -m scripts.adopt_legacy_database
python -m scripts.adopt_legacy_database --apply
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 终端 2（从仓库根目录开始）：前端
cd web
npm ci
npm run dev
```

```bash
# Linux / macOS / Git Bash：环境变量与基础设施
cp .env.example .env
docker compose up -d postgres redis

# 终端 1：后端
cd agent
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m scripts.adopt_legacy_database
python -m scripts.adopt_legacy_database --apply
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 终端 2（从仓库根目录开始）：前端
cd web
npm ci
npm run dev
```

`adopt_legacy_database` 第一次调用仅做诊断，`--apply` 会创建空库结构、升级已由
Alembic 管理的数据库，或在验证表结构兼容后安全接管旧版 `create_all` 数据库。

如需在宿主机后端中联调 MinIO，额外启动 `minio` 服务，并在 `.env` 中配置：

```dotenv
ARTIFACT_STORE_BACKEND=minio
MINIO_ENDPOINT=localhost:9000
MINIO_PUBLIC_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=<与 MINIO_USER 一致>
MINIO_SECRET_KEY=<与 MINIO_PASSWORD 一致>
```

```powershell
docker compose up -d postgres redis minio
```

打开浏览器访问：
- **前端**: http://localhost:5173
- **后端 API 文档**: http://localhost:8000/docs
- **MinIO 控制台**（启用 MinIO 时）: http://localhost:9001

### 知识库初始化（可选）

首次运行后，执行 embedding 播种脚本初始化 CS 术语向量库：
```bash
cd agent
python -m scripts.seed_embeddings
```

## 可复现工程基线

- 后端常规本地回归：**1174 passed，1 skipped，6 deselected**（真实 Manim 渲染和显式授权的在线评测按环境单独执行；symlink 能力按平台单独跳过）。
- 前端门禁：**42 files / 302 tests**，TypeScript、生产构建与 gzip Bundle Budget 通过；路由拆分后主入口由 1,342.14 kB 降至 547.38 kB（-59.2%）。
- EduFlowBench：50 个核心案例、8 个 Prompt Injection 案例、10 个检索案例、16 个确定性 Tool 案例及 8 个真实模型 Tool 在线案例。
- 上述数字是离线工程与数据集事实；真实模型质量、Tool 选择率、成本和延迟报告仍待显式凭据与成本授权，不以 fixture 分数替代。

## 文档索引

| 文档 | 说明 |
|------|------|
| [需求文档](docs/requirements/自主Agent教学推演系统_需求文档包_v1.md) | 用户故事、用例、功能边界 |
| [设计文档](docs/design/智能教学推演系统设计文档.md) | 完整技术方案（统一 LangGraph + DSL + 双路径渲染） |
| [核心功能模块全面改造方案](docs/design/核心功能模块全面改造方案.md) | 十大成果模块与统一成果工作台的改造蓝图 |
| [统一视觉改造方案](docs/design/统一视觉改造方案.md) | 全站视觉统一规范（宣传页 / 应用框架 / 成果组件） |
| [设计系统与前端规范](DESIGN.md) | 视觉/交互/实现指南（学术纸本 × 互动技术手稿） |
| [开发任务与接口规范](docs/开发任务与接口规范.md) | Phase 1-3 任务拆分 + API 契约 + DSL Schema 速查 |
| [术语表](docs/GLOSSARY.md) | 中英术语对照 |
| [贡献指南](CONTRIBUTING.md) | 分支策略与协作规范 |
| [工程化改造与 EduFlowBench 计划](docs/工程化改造与EduFlowBench实施计划.md) | 缺陷、优先级、验收标准与实施进度 |
| [当前与目标架构](docs/architecture.md) | 运行架构、目标演进图与 Agent 时序 |
| [故障案例矩阵](docs/failure-cases.md) | 已验证故障、防护和仍待运行的压力测试 |
| [故障注入基线](agent/evals/reports/fault-injection-v0.8.md) | 可复现故障场景、验证入口与外部环境待测项 |
| [ADR 0004：受控 Tool Runtime](docs/adr/0004-bounded-tool-runtime.md) | 只读能力面、身份注入、预算与 MCP 边界取舍 |
| [ADR 0005：持久化执行与事件流](docs/adr/0005-durable-execution-and-streams.md) | Checkpoint、lease、迟到写拒绝与 SSE 重放设计 |
| [安全威胁模型](docs/security/threat-model.md) | 上传、Prompt/Tool、解析、代码执行与下载的边界及剩余风险 |

## 开发

### 运行测试

```bash
# 后端测试（agent/ 目录下；测试数量以 pytest 实际收集结果为准）
cd agent
python -m pytest tests/ -m "not render and not online_eval" -v
python -m pytest tests/test_manim_render_smoke.py -m render -v  # 需要 Manim + FFmpeg
python -m pytest tests/ --cov=.      # 带覆盖率报告

# 前端测试（web/ 目录下）
cd web
npm test                             # 运行 Vitest（测试数量以实际报告为准）
npm run typecheck                    # TypeScript 类型检查（tsc -b，真实门禁）
npm run verify                       # 完整验证（类型 + 测试 + 构建）
npm run build                        # 生产构建
```

Python 顶层依赖声明位于 `agent/requirements.txt` 和 `agent/requirements-ci.txt`，
部署与 CI 使用由 uv 按 Python 3.12 生成的 `requirements*.lock.txt`。依赖声明变更后运行：

```bash
cd agent
uv pip compile requirements-ci.txt --python-version 3.12 --universal -o requirements-ci.lock.txt
uv pip compile requirements.txt --python-version 3.12 --universal -o requirements.lock.txt
```

### 环境变量

核心环境变量（详见 `.env.example`）：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BYOK_REQUIRED` | 固定为 `true`；模型调用只使用用户自己的接入配置 | `true` |
| `CREDENTIAL_KMS_BACKEND` | 生产为 `http`，通过内网 HTTPS KMS Bridge 调用云 KMS | `local`（仅开发） |
| `CREDENTIAL_KMS_WRAP_URL` / `CREDENTIAL_KMS_UNWRAP_URL` | 生产 KMS Bridge 固定地址 | - |
| `CREDENTIAL_KEK_B64` | 仅本地开发的 32 字节 base64 KEK | - |
| `METRICS_ACCESS_TOKEN` | 生产/预发布内部 Prometheus 抓取令牌；公网请求返回 404 | - |
| `RUN_MAINTENANCE` | 是否在 API 进程运行素材保留与注销处理；多副本 API 设为 `false`，单独运行 `maintenance` 服务 | `true` |
| `LLM_API_KEY` / `EMBEDDING_API_KEY` | 已停用；密钥必须由用户在“模型接入”中配置 | - |
| `DATABASE_URL` | 数据库连接字符串 | 手动开发有本地回退值；Compose 由必填 `DB_PASSWORD` 构造 |
| `REDIS_URL` | Redis 连接字符串 | `redis://localhost:6379` |
| `FFMPEG_PATH` | FFmpeg 安装目录（留空自动查找） | (空) |
| `AGENT_LOG_LEVEL` | Agent 日志级别 | `INFO` |

### 数据库迁移

业务表由 Alembic 管理（基线迁移 `agent/alembic/versions/0001_baseline.py`：8 张 ORM 表 + knowledge_base），
Docker Compose 由一次性 `migrate` 服务执行 `alembic upgrade head`，成功后才启动 API；
托管部署应使用同样的独立发布 Job，禁止每个 API 副本自行迁移。手动部署需先执行一次：

```bash
cd agent
# 开发环境推荐入口：识别空库、正常 Alembic 库，以及旧版 create_all 遗留库
# 默认只读检查；确认输出后加 --apply 执行安全接管/升级
python -m scripts.adopt_legacy_database
python -m scripts.adopt_legacy_database --apply

# 已由 Alembic 管理的部署也可直接执行
alembic upgrade head

# 默认只读检查版本、活动快照和 Frames 投影一致性
python -m scripts.audit_artifact_consistency

# 生成新迁移脚本（修改 db/models.py 后）
alembic revision --autogenerate -m "description"
```

---

## License

[Apache 2.0](LICENSE)
