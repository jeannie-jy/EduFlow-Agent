# EduFlow-Agent 后端

> FastAPI + LangGraph Multi-Agent 教学推演引擎

## 快速启动

```bash
# 系统依赖（视频导出需要）
# Windows: winget install Gyan.FFmpeg
# macOS:   brew install ffmpeg
# Linux:   apt install ffmpeg

# 创建虚拟环境（推荐 — 须用 Python 3.12，3.14 部分依赖无预编译 wheel）
python3.12 -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash / PowerShell
# .venv\Scripts\activate        # Windows CMD
# source .venv/bin/activate     # Linux / macOS

# 安装 Python 依赖
pip install -r requirements.txt

# 配置环境变量（确保仓库根目录有 .env）
cp ../.env.example ../.env

# 启动开发服务器
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API 文档: http://localhost:8000/docs

## 模块结构

```
agent/
├── main.py                   # FastAPI 应用入口（lifespan / CORS / 路由注册）
├── config.py                 # 配置模块（pydantic-settings，环境变量统一加载）
├── requirements.txt          # Python 依赖
├── Dockerfile                # Docker 镜像
│
├── agents/                   # LangGraph Agent 编排层
│   ├── state.py              # AgentState TypedDict（14 个共享字段）
│   ├── graph.py              # StateGraph 构建 + Checkpointer + 条件路由
│   ├── nodes.py              # 5 个 Agent 节点实现（planner / knowledge / coder / quality / reflection）
│   ├── prompts.py            # 5 个 Agent 的系统提示词
│   └── llm_client.py         # OpenAI 兼容客户端（DeepSeek）+ embedding 生成
│
├── api/                      # REST API 路由层
│   ├── router.py             # 路由聚合注册
│   ├── projects.py           # 项目 CRUD（POST/GET 列表/GET 详情）
│   ├── generate.py           # 生成流程（POST start / SSE stream / POST regenerate）
│   ├── frames.py             # 帧操作（GET 列表 / PUT 编辑 / POST lock）
│   ├── parameters.py         # 参数（GET 列表 / POST recompute）
│   ├── export.py             # 导出（POST manim 任务 / GET 状态 / GET 下载）
│   ├── knowledge.py          # 知识库（POST search / GET templates）
│   ├── feedback.py           # 反馈（POST 提交 / GET 列表 / 触发 Reflection）
│   ├── materials.py          # 素材（POST upload / POST parse / GET preview）
│   ├── versions.py           # 版本（POST 保存 / GET 列表 / GET 详情 / POST 恢复）
│   ├── error_handlers.py     # 全局异常处理（统一 {"error": {...}} 格式）
│   ├── middleware.py          # 请求日志 + request_id
│   └── deps.py               # UUID 解析等通用工具
│
├── schema/                   # Pydantic 数据模型
│   ├── dsl.py                # DSL Schema（renderScript / Frame / VisualObject×14 / Animation×16）
│   └── project.py            # API Request/Response 模型
│
├── db/                       # 数据库层
│   ├── database.py           # AsyncSession 工厂 + 读写分离
│   └── models.py             # SQLAlchemy ORM 模型（8 张表）
│
├── services/                 # 业务服务层
│   ├── generate_service.py   # SSE 流式生成编排（调用 LangGraph + 推送进度）
│   └── knowledge_service.py  # pgvector 语义检索 + embedding 播种
│
├── tools/                    # Agent 可调用的 Tool
│   ├── validate_dsl.py       # DSL Schema 校验 + 帧间状态一致性检查
│   ├── design_parameters.py  # 参数设计工具（8 种知识类型模板）
│   └── generate_asset.py     # 多模态资源生成（card/mindmap/table/code）
│
├── adapters/                 # DSL → Manim 转换器
│   ├── manim_adapter.py      # 确定性转换（14 种 Mobject + 16 种 Animation 映射）
│   ├── manim_llm_adapter.py  # LLM 驱动的 Manim 代码生成（教学语义 → 可视化脚本，当前默认）
│   ├── manim_validator.py    # Manim 脚本质量检测（6 项规则：语法/CJK/lexer/API/转义/print）
│   └── test_adapter.py       # 自测脚本（代码生成 + 语法校验 + 渲染验证）
│
├── plugins/                  # 领域插件系统
│   ├── domain_plugin.py      # DomainPlugin Protocol + 注册表
│   └── cs_plugin.py          # CS 内置插件（6 学科 + 5 教学策略 + 6 质量规则）
│
├── workers/                  # 后台 Worker
│   ├── render_worker.py      # Redis 队列消费者（DSL→Manim→MP4）
│   └── Dockerfile            # Manim Worker Docker 镜像
│
├── scripts/                  # 运维脚本
│   └── seed_embeddings.py    # 知识库 embedding 播种（seed → pgvector）
│
├── data/                     # 静态数据
│   └── seed_knowledge.json   # 22 个知识点种子数据
│
├── tests/                    # 测试（373 个）
│   ├── test_agent_nodes.py   # 5 个 Agent 节点 + Graph 拓扑
│   ├── test_api_integration.py  # API 集成测试
│   ├── test_db_integration.py   # 数据库 CRUD
│   ├── test_generate_service.py # 生成流程
│   ├── test_llm_client.py       # LLM 客户端
│   ├── test_schema.py           # DSL Schema 校验
│   ├── test_schema_edge_cases.py # Schema 边界案例
│   └── ...
│
└── alembic/                  # 数据库迁移（预留）
```

## Agent 协作流程

```
用户输入
    │
    ▼
┌─────────┐    ┌───────────┐    ┌────────┐    ┌─────────┐    ┌────────────┐
│ Planner │───►│ Knowledge │───►│ Coder  │───►│ Quality │───►│ Reflection │
│ 教学规划 │    │ 知识解析   │    │ 帧生成  │    │ 质量评估 │    │ 反思修订    │
└─────────┘    └───────────┘    └────────┘    └─────────┘    └────────────┘
                                          │
                                     Score < 60%
                                          │
                                     Reflection → Coder (重生成，上限 3 次)
```

- **Planner** → 输出 `teaching_plan`（目标/大纲/策略/风险）
- **Knowledge** → 输出 `knowledge_graph`（概念节点 + 关系边）+ `key_terms`
- **Coder** → 输出 `dsl`（完整 RenderScript：frames + parameters + assets）
- **Quality** → 输出 `quality_report`（3 层校验：Schema + 状态一致性 + LLM 六维度评分）
- **Reflection** → 分析问题 → 修订帧 → 回到 Coder 重生成

详见[设计文档 3.2 节](../docs/design/智能教学推演系统设计文档.md#32-agent-协作流程-langgraph)。

## API 总览

| 方法 | 端点 | 说明 |
|------|------|------|
| `POST` | `/api/projects` | 创建项目 |
| `GET` | `/api/projects` | 项目列表（分页 + 状态筛选） |
| `GET` | `/api/projects/{id}` | 项目详情（含完整 DSL） |
| `POST` | `/api/projects/{id}/generate` | 启动生成流程 |
| `GET` | `/api/projects/{id}/generate/stream` | SSE 流式进度 |
| `POST` | `/api/projects/{id}/regenerate` | 局部重生成 |
| `GET` | `/api/projects/{id}/frames` | 帧列表 |
| `PUT` | `/api/projects/{id}/frames/{fid}` | 编辑帧（locked 时 409） |
| `POST` | `/api/projects/{id}/frames/{fid}/lock` | 锁定/解锁帧 |
| `GET` | `/api/projects/{id}/parameters` | 参数列表 |
| `POST` | `/api/projects/{id}/recompute` | 参数变更触发重算 |
| `POST` | `/api/projects/{id}/export/manim` | 创建视频导出任务 |
| `GET` | `/api/export/{job_id}` | 查询导出状态 |
| `POST` | `/api/knowledge/search` | 语义检索（pgvector） |
| `GET` | `/api/knowledge/templates` | 知识点模板列表 |
| `POST` | `/api/materials/upload` | 上传课件文件 |
| `POST` | `/api/materials/{id}/parse` | 解析文件内容 |
| `POST` | `/api/projects/{id}/feedback` | 提交反馈 |
| `POST` | `/api/projects/{id}/versions` | 保存版本 |
| `GET` | `/api/projects/{id}/versions` | 版本列表 |
| `GET` | `/api/projects/{id}/versions/{vid}` | 版本详情 |
| `POST` | `/api/projects/{id}/versions/{vid}/restore` | 恢复版本 |

完整契约见[开发任务与接口规范](../docs/开发任务与接口规范.md)。

## 配置

所有配置通过环境变量加载（`config.py` → pydantic-settings），支持 `.env` 文件。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | — | DeepSeek API Key（**必填**） |
| `LLM_ENDPOINT` | `https://api.deepseek.com/v1` | LLM API 地址 |
| `LLM_MODEL` | `deepseek-chat` | 模型名称 |
| `EMBEDDING_API_KEY` | — | OpenAI API Key |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | 嵌入模型 |
| `DATABASE_URL` | `postgresql+asyncpg://...` | 数据库连接 |
| `REDIS_URL` | `redis://localhost:6379` | Redis 连接 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `AGENT_MAX_RETRIES` | 3 | Agent 重试次数 |
| `QUALITY_SCORE_THRESHOLD` | 0.6 | Quality 阈值（低于触发 Reflection） |
| `FFMPEG_PATH` | (空) | FFmpeg 安装目录，留空则自动从 PATH 查找 |
| `MAX_REFLECTION_CYCLES` | 3 | Reflection 最大循环次数 |

## 测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 仅 Agent 节点测试
python -m pytest tests/test_agent_nodes.py -v

# 仅 API 集成测试
python -m pytest tests/test_api_integration.py -v

# 带覆盖率
python -m pytest tests/ --cov=. --cov-report=html
```

测试统计: 373 个测试（15 个文件），覆盖 Agent 节点、API 集成、数据库 CRUD、DSL Schema、LLM 客户端、生成流程。

## 数据流

```
1. POST /api/projects           → 创建项目，存 DB
2. POST /{id}/generate          → 启动 Agent 编排流程
3. GET  /{id}/generate/stream   → SSE 订阅进度
   ├── planner   → teaching_plan
   ├── knowledge → knowledge_graph
   ├── coder     → dsl (frames + parameters + assets)
   ├── quality   → quality_report
   └── reflection → 修订（循环上限 3 次）
4. GET  /{id}                   → 获取最终 DSL
5. POST /{id}/export/manim      → 导出视频（异步队列）
```

## 错误响应格式

所有错误统一返回：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "帧间状态不一致: f_005 的 distance_table 与 f_004 不匹配",
    "details": { "field_errors": {} }
  }
}
```

## 知识库初始化

```bash
# 播种 22 个知识点的 embedding 到 pgvector
python -m scripts.seed_embeddings
```
