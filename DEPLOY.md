# EduFlow-Agent 部署指南

## 环境要求

- Docker 24+
- Docker Compose v2
- 4 GB 可用内存（启用独立 Manim Worker 后，1080p 导出较吃内存）
- 10 GB 磁盘空间

## 快速启动

### 方式一：一键脚本

**Windows PowerShell：**
```powershell
copy .env.example .env
# 编辑 .env：替换 DB_PASSWORD、MINIO_USER、MINIO_PASSWORD，
# 并填入 LLM_API_KEY 和 EMBEDDING_API_KEY
# HTTPS 部署同时设置 AUTH_COOKIE_SECURE=true
.\start.ps1
```

**Linux / macOS / Git Bash：**
```bash
cp .env.example .env
# 编辑 .env，填入 API Key
chmod +x start.sh
./start.sh
```

### 方式二：Docker Compose

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/EduFlow-Agent.git
cd EduFlow-Agent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env：替换 DB_PASSWORD、MINIO_USER、MINIO_PASSWORD，
# 并填入 LLM_API_KEY 和 EMBEDDING_API_KEY

# 3. 启动默认服务（视频导出保持关闭）
docker compose up -d

# 可选：显式启用视频导出 Worker
MANIM_EXECUTION_MODE=queue docker compose --profile video up -d

# 可选：启用 Prometheus + Grafana；先修改 GRAFANA_ADMIN_PASSWORD
docker compose --profile observability up -d

# 4. 验证
curl http://localhost:8000/api/health
# → {"status":"ok","version":"0.8.0"}
```

## 服务架构

| 服务 | 端口 | 说明 |
|------|------|------|
| `web` | 5173 | Nginx 前端与 `/api` 反向代理 |
| `agent-api` | 8000 | FastAPI 后端（Agent 编排 + REST API，启动时自动执行数据库迁移） |
| `postgres` | 5432 | PostgreSQL 16 + pgvector（向量检索） |
| `redis` | 6379 | Redis 7（导出状态追踪 + 缓存） |
| `minio` | 9000, 9001 | MinIO 对象存储（导出产物、上传素材与短期签名下载） |
| `task-worker` | 无 | 持久化 Agent 任务与材料下载/签名准备器 |
| `material-sandbox` | 无 | 无网络、无服务凭据的材料解析沙箱 |
| `render-worker` | 无 | 可选数据库 lease 消费者，仅在 `video` profile 启动 |
| `render-sandbox` | 无 | 可选无网络、无凭据 Manim 执行器，仅在 `video` profile 启动 |
| `prometheus` | 9090（仅回环） | 可选 24 小时运营指标抓取与告警规则 |
| `grafana` | 3000（仅回环） | 可选预置 EduFlow Agent Operations 面板 |

> 注：API 只持久化导出任务，不执行模型生成的 Python。准备器生成并校验脚本，
> 再通过共享任务目录交给 `network_mode: none` 的无凭据沙箱执行。
> 材料解析采用同样的权限拆分：task-worker 下载并签名，material-sandbox 验签并解析。

## 常用命令

```bash
docker compose up -d              # 启动全部服务
docker compose down               # 停止全部服务
docker compose logs -f agent-api  # 查看后端日志
docker compose logs -f render-worker # 查看视频导出日志
docker compose logs -f render-sandbox # 查看沙箱日志
docker compose ps                 # 查看服务状态
docker compose restart agent-api  # 重启后端
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|:---:|------|
| `LLM_API_KEY` | ✅ | DeepSeek API Key |
| `EMBEDDING_API_KEY` | ✅ | OpenAI API Key（text-embedding-3-small） |
| `LLM_ENDPOINT` | — | LLM API 地址（默认 `https://api.deepseek.com/v1`） |
| `LLM_MODEL` | — | 模型名称（默认 `deepseek-chat`） |
| `DB_PASSWORD` | ✅ | 数据库密码；Compose 无回退默认值 |
| `REDIS_URL` | — | Redis 连接（默认 `redis://localhost:6379`） |
| `MINIO_USER` / `MINIO_PASSWORD` | ✅ | MinIO 凭证；Compose 无回退默认值 |
| `MINIO_PUBLIC_ENDPOINT` | `localhost:9000` | 浏览器可访问的 MinIO 地址；反向代理或远程部署时必须改为外部地址 |

## 本地开发

```bash
# 仅启动基础设施（数据库 + Redis + MinIO）
docker compose up -d postgres redis minio

# 或使用启动脚本
./start.sh infra        # Linux/macOS
.\start.ps1 -Infra      # Windows

# 手动启动后端（hot reload）
cd agent
pip install -r requirements.lock.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 --reload-dir agents --reload-dir api --reload-dir adapters --reload-dir db --reload-dir generators --reload-dir plugins --reload-dir schema --reload-dir services --reload-dir tools --reload-dir alembic --reload-dir scripts --reload-dir main.py

# 手动启动前端（hot reload）
cd web
npm install
npm run dev

# 视频链路包含准备器与无网络沙箱，推荐统一由 Compose profile 启动
MANIM_EXECUTION_MODE=queue docker compose --profile video up -d

# 知识库初始化
cd agent
python -m scripts.seed_embeddings
```

### 首次管理员引导

先通过注册页创建目标账号，再在 API 容器或已配置同一数据库的后端环境执行：

```bash
cd agent
python -m scripts.bootstrap_admin --email admin@example.com
```

该命令只在系统尚无有效管理员时允许提升账号，并撤销该账号的旧登录会话、写入审计事件；
重新登录后可在 `/app/admin/users` 管理角色、账号状态和会话。已有有效管理员时，命令拒绝
提升其他账号，必须使用受认证的管理员页面。HTTPS 部署还必须设置
`AUTH_COOKIE_SECURE=true`。

从早期无认证版本升级时，先只读盘点，再显式应用 owner 归属；如仍有
`storage_key=NULL` 的本地素材，可在同一次迁移中复制到当前 ArtifactStore。原文件不会删除：

```bash
python -m scripts.migrate_legacy_data --owner-email admin@example.com --migrate-material-files
python -m scripts.migrate_legacy_data --owner-email admin@example.com --migrate-material-files --apply
```

应用前会预检全部本地素材路径与文件是否存在，任一缺失都不会提交数据库变更；文件大小与
数据库元数据不一致时也会失败。请先备份数据库，并根据 dry-run 输出确认接收 owner。

### 审计保留与签名归档

在 `.env` 中配置至少 32 字符、单独备份的 `AUDIT_ARCHIVE_HMAC_KEY`。先预览超过保留期的
事件，再生成 SHA-256 hash chain + HMAC manifest；只有从 ArtifactStore 回读并验证成功后，
`--purge-after-verify` 才会删除本批精确 ID，且数据库会保留归档索引事件：

```bash
docker compose exec agent-api python -m scripts.archive_audit_events
docker compose exec agent-api python -m scripts.archive_audit_events --apply
docker compose exec agent-api python -m scripts.archive_audit_events --apply --purge-after-verify
```

默认保留 90 天、每批最多 10000 条，可通过 `AUDIT_RETENTION_DAYS`、
`AUDIT_ARCHIVE_MAX_EVENTS` 或命令参数调整。归档保存在 `audit-archives/`，应为该前缀配置
对象锁、版本控制和独立生命周期策略；HMAC 密钥不可与对象存储凭据一同归档。

## 健康检查

| 端点 | 说明 |
|------|------|
| `GET /api/health` | 后端健康状态 |
| `GET /api/ready` | PostgreSQL、Redis 与当前 ArtifactStore readiness |
| `GET /api/ping` | 轻量 ping |
| `GET /api/knowledge/templates` | 知识库就绪确认 |
| `GET /api/metrics` | 进程指标与 PostgreSQL 跨进程聚合（仅直接访问 API） |
| `GET /api/metrics/prometheus` | Prometheus 抓取端点；Nginx 公网代理显式返回 404 |
| `GET /docs` | Swagger API 文档 |

### Compose 依赖故障验收

在专用测试环境启动完整 Compose 栈后，可依次真实停止 Redis、PostgreSQL 与
MinIO，验证 API 进程仍存活、readiness 能定位故障且服务恢复后重新就绪：

```bash
python agent/scripts/compose_fault_smoke.py \
  --services redis postgres minio \
  --report fault-smoke-report.json
```

该命令会修改正在运行的容器状态，请勿指向生产环境。脚本在失败路径也会尝试
恢复被停止的服务；GitHub Actions 中可手动运行 `Compose Fault Injection`，其
隔离栈会在结束时删除并上传 JSON 报告、容器状态和日志。此验收不调用 LLM，
真实模型 Tool Calling 使用 EduFlowBench 的显式 opt-in online runner 单独执行。

同一专用环境还可执行无模型费用、只读的 HTTP/依赖容量 smoke：

```bash
python agent/scripts/http_capacity_smoke.py \
  --duration 60 --concurrency 16 \
  --report capacity-smoke-report.json
```

报告包含总体及逐端点 RPS、错误率、p50/p95/p99 和状态分布。默认覆盖 health、
readiness 与 Prometheus 聚合端点；它用于发现明显的 API/DB/Redis/MinIO 容量退化，
不等价于带真实 Agent 任务的多副本长时间 soak。

## 端口一览

| 服务 | 端口 | URL |
|------|------|-----|
| 前端 (Vite) | 5173 | http://localhost:5173 |
| 后端 (FastAPI) | 8000 | http://localhost:8000 |
| API 文档 | 8000 | http://localhost:8000/docs |
| PostgreSQL | 5432 | `postgresql://agent:<DB_PASSWORD>@localhost:5432/eduflow` |
| Redis | 6379 | redis://localhost:6379 |
| MinIO API | 9000 | http://localhost:9000 |
| MinIO Console | 9001 | http://localhost:9001 |

## 故障排查

```bash
# 数据库连接失败
docker compose logs postgres

# 视频导出失败
# 1) 查看独立 Worker 日志
docker compose logs -f render-worker
# 2) 渲染错误完整记录在对应任务目录：data/exports/{job_id}/render_error.log

# 后端 Agent 错误
docker compose logs agent-api

# 清理重建
docker compose down -v
docker compose up -d --build
```
