# EduFlow-Agent 部署指南

## 环境要求

- Docker 24+
- Docker Compose v2
- 4 GB 可用内存（含 Manim Worker）
- 10 GB 磁盘空间

## 快速启动

### 方式一：一键脚本

**Windows PowerShell：**
```powershell
copy .env.example .env
# 编辑 .env，填入 LLM_API_KEY 和 EMBEDDING_API_KEY
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
# 编辑 .env，填入 LLM_API_KEY 和 EMBEDDING_API_KEY

# 3. 一键启动全部服务
docker compose up -d

# 4. 验证
curl http://localhost:8000/api/health
# → {"status":"ok","version":"0.1.0"}
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
|------|:---:|------|
| `LLM_API_KEY` | ✅ | DeepSeek API Key |
| `EMBEDDING_API_KEY` | ✅ | OpenAI API Key（text-embedding-3-small） |
| `LLM_ENDPOINT` | — | LLM API 地址（默认 `https://api.deepseek.com/v1`） |
| `LLM_MODEL` | — | 模型名称（默认 `deepseek-chat`） |
| `DB_PASSWORD` | — | 数据库密码（默认 `changeme`） |
| `REDIS_URL` | — | Redis 连接（默认 `redis://localhost:6379`） |
| `MINIO_USER` / `MINIO_PASSWORD` | — | MinIO 凭证（默认 `minioadmin`） |

## 本地开发

```bash
# 仅启动基础设施（数据库 + Redis + MinIO）
docker compose up -d postgres redis minio

# 或使用启动脚本
./start.sh infra        # Linux/macOS
.\start.ps1 -Infra      # Windows

# 手动启动后端（hot reload）
cd agent
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 手动启动前端（hot reload）
cd web
npm install
npm run dev

# 手动启动 Manim Worker（需要先 pip install manim redis）
cd agent
python workers/render_worker.py

# 知识库初始化
cd agent
python -m scripts.seed_embeddings
```

## 健康检查

| 端点 | 说明 |
|------|------|
| `GET /api/health` | 后端健康状态 |
| `GET /api/ping` | 轻量 ping |
| `GET /api/knowledge/templates` | 知识库就绪确认 |
| `GET /api/docs` | Swagger API 文档 |

## 端口一览

| 服务 | 端口 | URL |
|------|------|-----|
| 前端 (Vite) | 5173 | http://localhost:5173 |
| 后端 (FastAPI) | 8000 | http://localhost:8000 |
| API 文档 | 8000 | http://localhost:8000/docs |
| PostgreSQL | 5432 | postgresql://agent:changeme@localhost:5432/eduflow |
| Redis | 6379 | redis://localhost:6379 |
| MinIO API | 9000 | http://localhost:9000 |
| MinIO Console | 9001 | http://localhost:9001 |

## 故障排查

```bash
# 数据库连接失败
docker compose logs postgres

# Manim 渲染失败
docker compose logs manim-worker

# 后端 Agent 错误
docker compose logs agent-api

# 清理重建
docker compose down -v
docker compose up -d --build
```
