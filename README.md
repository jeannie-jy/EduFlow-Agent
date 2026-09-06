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
[![Version](https://img.shields.io/badge/version-0.9.0-informational.svg)]()

---

## 当前状态

> **v0.9.0 — Agent 工程化闭环 + EduFlowBench**
>
> 统一 LangGraph 工作流、受控 Tool Calling、RAG、HITL、质量反思、持久化执行与评测链路已完成工程化收口。

**本次更新 (v0.9.0)：**
- 🧩 **生成方式可选化**：10 种模块生成器（思维导图/知识卡片/交互推演/小练习/对比分析/常见误区/学习路径/代码沙箱/教学视频 + 自动生成的推演脚本），按需勾选生成
- 🎨 **UI 流程重塑**：步骤指示器（select → plan → results）替代 Tab 栏，新建流程统一收拢到 ProjectWorkspace
- 🛡️ **数据库初始化落地**：Alembic 基线迁移（8 张业务表 + knowledge_base），agent-api 启动时自动 `alembic upgrade head`，不再依赖 init.sql 建表
- 🔧 **前端类型门禁**：`npm run typecheck` 改为 `tsc -b`（此前对 solution tsconfig 是空操作），34 个存量 TS 错误清零；修复 SSE 模块事件回调解构缺失（模块进度此前被静默丢弃）
- 🎬 **视频导出任务化**：API 只持久化排队，独立受限 Worker 通过 PostgreSQL lease 领取、重试和恢复任务；默认关闭，需显式启用 video profile
- 🧪 **测试覆盖扩展**：当前后端测试规模超过 790 项，前端包含 39 个测试文件；准确数量以测试框架报告为准，CI 分离运行快速测试与真实 Manim 渲染冒烟测试
- 🎁 **成果体验统一**：交互推演升级为统一学习外壳（按主题语义匹配 7 种体验类型）；教学视频支持从推演帧直接定位分镜；失败模块以场景化友好提示呈现（额度不足/接入失效/限流/网络/渲染失败），可在成果页直接重生成
- 🖥️ **交互推演沙箱升级**：Tailwind 在宿主侧按产物实际使用的 class 本地编译（彻底移除 CDN 依赖），内置 `eduflow-demo` 统一演示样式，遗留模板控件自动打磨为设计系统风格
- 🧬 **成果版本追踪**：推演脚本产出携带 `artifact_version`（SHA-256），视频产出记录 `source_frames_version`；帧编辑同步快照与模块产出两处副本，分镜过期时提示「分镜已更新」
- 🔐 **真实后端会话**：注册/登录使用 scrypt 密码散列与仅存散列的 HttpOnly opaque session；Compose 默认保护业务 API，并按项目 owner 隔离项目路径与导出产物
- 📁 **素材治理**：上传文件记录 owner 与到期时间，校验 PDF/PPTX/文本内容签名，支持删除和定时保留期清理，解析不阻塞 API 事件循环
- 🧾 **关键操作审计**：账号注册/登录、项目创建/删除、素材上传/删除及视频排队写入只追加审计事件，并关联 request ID
- 🧭 **LLM 提示词防漂移**：生成请求显式声明主题权威边界（示例仅描述输出形状），对比分析泛化支持算法/概念/机制/协议/用户自定义主题

**历史版本：**
- **v0.8.0 — 模块化生成主线 + 可靠性加固**：10 种模块化教学产物、任务化视频导出、真实后端会话、素材治理、成果版本追踪与关键操作审计
- **v0.7.0 — 前端重设计 + 安全加固**：Landing 叙事页、Dijkstra 公开探索页、纸张质感主题系统、无障碍增强、130 个前端测试 + 373 个后端测试
- **v0.6.0 — LLM 驱动 Manim**：教学语义 → LLM 自主设计可视化布局/配色/动画、Manim 脚本 6 项静态质量检测 + 自动修复 + 失败重试、双模式渲染雏形

**下一阶段规划：**
- 🎨 **成果工作台深化**：继续推进可编辑、可校验、可发布的教学成果闭环（帧编辑器、成果校验视图、发布流程）
- ⚡ **时效优化**：生成链路响应速度（LLM 调用并行化、SSE 进度细化、模块调度并发）、前端加载性能（代码分割、沙箱运行时懒加载）
- 🚀 **并发视频导出**：当前单轨导出并发上限 2（见「已知局限」），计划引入 Celery/RQ 任务队列或重建独立渲染 Worker
- 🎓 **模板库扩充**：更多公开教学案例与按知识点预置的生成模板
- 🎬 **导出视频优化**：修复视频排版问题，确保视频元素不重叠、不截断

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
- **模块化产出**：教学计划生成后按需勾选成果模块（思维导图 / 知识卡片 / 交互推演 / 对比分析 / 教学视频等），逐帧推演脚本作为基础成果自动生成

## 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| **LLM** | DeepSeek (主) | API 调用（兼容 OpenAI 接口），`LLM_MODEL` 可切换（默认 `deepseek-v4-flash`） |
| **Embedding** | text-embedding-3-small (1536维) | 知识库语义检索，可平替通义千问 text-embedding-v4 |
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
# 编辑 .env：替换数据库/MinIO 凭证，并填入 LLM 与 Embedding API Key

# 启动基础设施、后端和前端（不传参等价于 -All）
.\start.ps1
```

**Linux / macOS / Git Bash：**

```bash
# 首次使用：配置环境变量并创建 Python 3.12 虚拟环境
cp .env.example .env
python3.12 -m venv agent/.venv
# 编辑 .env，替换数据库/MinIO 凭证并填入 API Key

chmod +x start.sh
./start.sh
```

也可按模块启动。`Backend` 模式要求 PostgreSQL/Redis 已运行，`Frontend` 模式要求后端已运行：

```powershell
# Windows PowerShell
.\start.ps1 -Infra
.\start.ps1 -Backend
.\start.ps1 -Frontend
.\start.ps1 -All
```

```bash
# Linux / macOS / Git Bash
./start.sh infra
./start.sh backend
./start.sh frontend
./start.sh all
```

### 方式二：Docker Compose（完整应用容器化）

```powershell
Copy-Item .env.example .env
# 编辑 .env：必须替换 DB_PASSWORD、MINIO_USER 和 MINIO_PASSWORD，按需填入 API Key
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
| `agent-api` | 8000 | FastAPI 后端 API（启动时自动执行数据库迁移） |
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

- 后端完整本地回归：**1051 passed**（Python 3.12 虚拟环境，含真实 Manim 渲染用例）；无跳过测试。
- 前端门禁：**41 files / 295 tests**，TypeScript、生产构建与 gzip Bundle Budget 通过；路由拆分后主入口由 1,342.14 kB 降至 547.38 kB（-59.2%）。
- EduFlowBench：50 个核心案例、8 个 Prompt Injection 案例、10 个检索案例、16 个确定性 Tool 案例及 8 个真实模型 Tool 在线案例。
- 上述数字是离线工程与数据集事实；真实模型质量、Tool 选择率、成本和延迟报告仍待显式凭据与成本授权，不以 fixture 分数替代。

## 已知局限与后续可拓展思路

- **真实 Tool Calling 已进入 Knowledge 主链**：模型可在有界多轮循环中自主选择 `knowledge_search`、`material_lookup`、`get_project_context`，经 Pydantic Schema、服务端 actor/project 上下文、owner 策略、超时/轮数/进程级共享并发/调用数/结果大小预算后执行真实服务，并把结构化 ToolResult 回填继续推理。每次调用以迁移 `0013` 持久化脱敏 Tool Trace，EduFlowBench 已加入 16 个选择、无工具、参数、故障、权限、注入与预算案例；Shell、任意 SQL、任意文件和写工具不在 Registry。真实模型 Tool Bench 基线仍需凭据与成本授权。
- **真实模型 Tool Bench 具备显式执行入口**：`tool_online_cases.jsonl` 的 8 个在线案例通过 `live_tools` 适配器直接调用生产 Tool Runtime，并记录选择、执行状态、多轮 Token、估算成本和 p95；手动 `Online Tool Calling Bench` 工作流只在提供评测 Secrets 后运行，使用隔离 Compose 数据库并上传可审计报告。仓库尚未取得凭据与成本授权，因此不宣称已有真实模型分数。
- **核心质量 Bench 已接入生产 Graph 与独立 Judge**：`live_workflow` 将 50 个核心案例直接送入 Planner–Knowledge–Coder–Quality–Reflection LangGraph；`live_judge` 使用独立 endpoint/key/model 完成七维盲评，并把候选与 Judge Token/成本分开记录。手动 `Online EduFlowBench Quality` 工作流使用隔离依赖并上传报告、产物和日志；总成本达到阈值后停止新案例/Judge。真实运行与人工校准完成前不宣称语义质量分数。
- **授权管理边界**：后端已有 student/teacher/admin RBAC、owner 隔离、scrypt 密码散列与 HttpOnly opaque session；登录/注册、普通写操作及高成本生成入口分别使用 Redis 优先的固定窗口限流，Redis 故障时退化到有界进程内计数。高风险写操作仅 teacher/admin 可用，admin 可跨 owner 管理；管理员页面支持角色/账号状态调整和全会话撤销，服务端阻止自我降权及移除最后一名有效管理员，变更会撤销旧会话并写审计。首次管理员使用一次性 bootstrap 命令建立；存量 owner/本地素材通过 dry-run 优先的显式迁移命令处理。当前自助注册默认 teacher；HTTPS 部署必须设置 `AUTH_COOKIE_SECURE=true`。
- **视频导出仍需继续加固**：API 只创建持久化任务，准备器通过数据库 lease 串行领取，无网络、无凭证沙箱执行生成代码；已有幂等键、逐次 attempt、lease 心跳、取消、可重试错误分类、指数退避和每任务磁盘/文件数配额。沙箱当前仍为常驻容器及共享任务卷，还需补每任务临时容器、更完整的恶意脚本和压力验证。
- **参数重算已具备跨产物影响分析**：`local` 参数原子校验后直接应用；结构性参数使用 DSL 显式依赖与结构化引用推断，从最早受影响帧开始重算状态后继，无法证明依赖时安全降级为全量。影响会沿生成器 `requires` DAG 传播到下游模块，UI 在写入前展示重算/保留范围及过期产物，并用影响指纹阻止并发状态变化后的过期执行；成功重生成后清除对应 stale 标记。
- **版本与帧投影已收敛**：Frames 表是活动编辑真源，`ProjectVersion` 保存不可变聚合快照，`current_version_id` 在项目行锁内推进；dirty working copy、恢复和导出固定版本语义明确。`module_outputs.frames` 仅存 artifact reference，迁移 0020 归一化存量 JSONB，读取时按需水合兼容结构；`python -m scripts.audit_artifact_consistency` 可只读核对指针、快照与 Frames 投影。
- **材料解析已持久化并隔离执行**：上传素材通过 `ArtifactStore` 写入 MinIO，解析 API 只幂等创建 owner-scoped `material_parse` 任务；带凭据 Worker 使用 lease/heartbeat 下载并签署文件，再交给无网络、无服务凭据、受 CPU/内存/PID 约束的 `material-sandbox`。沙箱复核 SHA-256，结果通过 Schema/大小边界后，Worker 在仍持有任务所有权时原子写回。生成只读取数据库中的已解析结果；旧 `data/uploads` 已有保留源文件、预检后显式执行的迁移工具，真实部署数据迁移与 MinIO 容器集成报告仍待完成。
- **SSE 事件支持跨进程重放**：每次生成使用独立 `stream_id`，事件发送前写入 PostgreSQL 账本，包含单调 `id`、`event_id` 和 `schema_version`；前端按标准 SSE frame 解析并以 `Last-Event-ID` 自动重连去重。生产者通过可续租 lease 排他执行，正常断连释放，进程崩溃后可超时接管；终态流只重放、不重新执行。页面优先从 `sessionStorage` 恢复 URL 和游标，本地状态缺失时可在 owner 校验后从服务端发现项目活动流；等待审批状态由项目快照恢复。部分非主 Graph 模块接管时的细粒度 checkpoint 仍未实现。
- **可观测性已具备本地运营闭环**：主生成、恢复、局部重生成和反馈 Reflection Worker 持久化 workflow/node Trace；Tool Calling 记录脱敏参数/结果摘要、状态与耗时。`/api/metrics/prometheus` 从 PostgreSQL 聚合 24 小时工作流成功率/p95、节点 Token/成本、工具错误、队列等待、导出与 SSE 状态；可选 Compose profile 提供 Prometheus、告警规则和 Grafana 面板。尚未接入 OpenTelemetry Collector、外部通知渠道和长期指标仓库。
- **模块生成入口已统一且支持成本预检**：首次生成、单模块重试和批量失败重试均进入同一 LangGraph Modules 节点，由 Graph 收尾执行唯一一次快照/版本持久化；重试前按最近成功 Trace 的单模块费用中位数展示非约束性估算。没有有效计价样本时明确显示“不可估算”，并单独展示 Token/成本硬上限。

## 文档索引

| 文档 | 说明 |
|------|------|
| [需求文档](docs/requirements/自主Agent教学推演系统_需求文档包_v1.md) | 用户故事、用例、功能边界 |
| [设计文档](docs/design/智能教学推演系统设计文档.md) | 完整技术方案（Multi-Agent + DSL + 双路径渲染） |
| [核心功能模块全面改造方案](docs/design/核心功能模块全面改造方案.md) | 十大成果模块与统一成果工作台的改造蓝图 |
| [统一视觉改造方案](docs/design/统一视觉改造方案.md) | 全站视觉统一规范（宣传页 / 应用框架 / 成果组件） |
| [设计系统与前端规范](DESIGN.md) | 视觉/交互/实现指南（学术纸本 × 互动技术手稿） |
| [开发任务与接口规范](docs/开发任务与接口规范.md) | Phase 1-3 任务拆分 + API 契约 + DSL Schema 速查 |
| [术语表](docs/GLOSSARY.md) | 中英术语对照 |
| [贡献指南](CONTRIBUTING.md) | 分支策略与协作规范 |
| [工程化改造与 EduFlowBench 计划](docs/工程化改造与EduFlowBench实施计划.md) | 缺陷、优先级、验收标准与实施进度 |
| [简历证据清单](docs/resume-evidence.md) | 可引用工程数据、禁用指标与 Agent 实习最终推荐版 |
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
| `LLM_API_KEY` | DeepSeek API Key | - |
| `LLM_MODEL` | LLM 模型名称 | `deepseek-v4-flash` |
| `EMBEDDING_API_KEY` | Embedding API Key | - |
| `DATABASE_URL` | 数据库连接字符串 | 手动开发有本地回退值；Compose 由必填 `DB_PASSWORD` 构造 |
| `REDIS_URL` | Redis 连接字符串 | `redis://localhost:6379` |
| `FFMPEG_PATH` | FFmpeg 安装目录（留空自动查找） | (空) |
| `AGENT_LOG_LEVEL` | Agent 日志级别 | `INFO` |

### 数据库迁移

业务表由 Alembic 管理（基线迁移 `agent/alembic/versions/0001_baseline.py`：8 张 ORM 表 + knowledge_base），
Docker 部署时 `agent-api` 启动前会自动执行 `alembic upgrade head`；手动部署需先执行一次：

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
