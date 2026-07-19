# EduFlow-Agent 部署指南

## 环境要求

- Docker 24+
- Docker Compose v2
- 4 GB 可用内存（含 Manim Worker）
- 10 GB 磁盘空间

## 快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/EduFlow-Agent.git
cd EduFlow-Agent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY 和 EMBEDDING_API_KEY

# 3. 一键启动
docker compose up -d

# 4. 验证
curl http://localhost:8000/api/health
```

## 服务架构

| 服务 | 端口 | 说明 |
|------|------|------|
| `agent-api` | 8000 | FastAPI 后端（Agent 编排 + REST API） |
| `postgres` | 5432 | PostgreSQL 16 + pgvector（向量检索） |
| `redis` | 6379 | Redis 7（任务队列 + 缓存） |
| `manim-worker` | — | Manim 视频渲染 Worker（Docker 隔离） |
| `minio` | 9000, 9001 | MinIO 对象存储（上传文件 + 渲染产物） |

## 常用命令

```bash
docker compose up -d              # 启动全部服务
docker compose down               # 停止全部服务
docker compose logs -f agent-api  # 查看后端日志
docker compose ps                 # 查看服务状态
docker compose restart agent-api  # 重启后端
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `LLM_API_KEY` | ✅ | DeepSeek API Key |
| `EMBEDDING_API_KEY` | ✅ | OpenAI API Key（text-embedding-3-small） |
| `DB_PASSWORD` | — | 数据库密码（默认 `changeme`） |
| `LLM_MODEL` | — | 模型名称（默认 `deepseek-chat`） |
| `MINIO_USER` / `MINIO_PASSWORD` | — | MinIO 凭证（默认 `minioadmin`） |

## 本地开发

```bash
# 仅启动基础设施（数据库 + Redis + MinIO）
docker compose up -d postgres redis minio

# 本地启动后端（hot reload）
cd agent
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 手动启动 Manim Worker（需要先 pip install manim）
python workers/render_worker.py
```

## 健康检查

| 端点 | 说明 |
|------|------|
| `GET /api/health` | 后端健康状态 |
| `GET /api/ping` | 轻量 ping |
| `GET /api/knowledge/templates` | 知识库就绪确认 |

## 故障排查

```bash
# 数据库连接失败
docker compose logs postgres

# Manim 渲染失败
docker compose logs manim-worker

# 清理重建
docker compose down -v
docker compose up -d --build
```
