#!/usr/bin/env bash
# EduFlow-Agent 一键启动脚本 (Linux / macOS / Git Bash)
# 用法: ./start.sh [infra|backend|frontend|all]
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

MODE="${1:-all}"

echo -e "\033[36m========================================\033[0m"
echo -e "\033[36m  EduFlow-Agent 启动\033[0m"
echo -e "\033[36m========================================\033[0m"

# ── 1. 检查 .env ──────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo -e "\033[33m[!] 未找到 .env 文件，从 .env.example 复制...\033[0m"
    cp .env.example .env
    echo -e "\033[33m[!] 请编辑 .env 填入 API Key，然后重新运行\033[0m"
    echo -e "\033[33m    LLM_API_KEY=your-deepseek-api-key\033[0m"
    echo -e "\033[33m    EMBEDDING_API_KEY=your-openai-api-key\033[0m"
    exit 1
fi

# ── 2. 启动基础设施（Docker）────────────────────────────────
if [[ "$MODE" =~ ^(all|infra)$ ]]; then
    echo -e "\n\033[32m[1/3] 启动基础设施 (PostgreSQL + Redis + MinIO)...\033[0m"
    docker compose up -d postgres redis minio
    echo "  -> PostgreSQL: localhost:5432"
    echo "  -> Redis: localhost:6379"
    echo "  -> MinIO: localhost:9000 (Console: :9001)"

    echo "  等待 PostgreSQL 就绪..."
    for i in $(seq 1 15); do
        if docker compose exec -T postgres pg_isready -U agent -d eduflow >/dev/null 2>&1; then
            break
        fi
        sleep 2
    done
    echo "  -> PostgreSQL 已就绪"
fi

# ── 3. 启动后端 ──────────────────────────────────────────
if [[ "$MODE" =~ ^(all|backend)$ ]]; then
    echo -e "\n\033[32m[2/3] 启动后端 (FastAPI)...\033[0m"
    cd "$PROJECT_ROOT/agent"

    # 检查虚拟环境
    if [ -f ".venv/bin/activate" ]; then
        echo "  -> 激活虚拟环境 .venv"
        source .venv/bin/activate
    fi

    # 检查依赖
    python -c "import fastapi" 2>/dev/null || pip install -r requirements.txt

    echo "  -> FastAPI 启动在 http://localhost:8000"
    echo "  -> API 文档: http://localhost:8000/docs"

    # 后台启动
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-exclude 'data/*' --log-level info &
    BACKEND_PID=$!
    echo "  -> 后端 PID: $BACKEND_PID"
fi

# ── 4. 启动前端 ──────────────────────────────────────────
if [[ "$MODE" =~ ^(all|frontend)$ ]]; then
    echo -e "\n\033[32m[3/3] 启动前端 (Vite)...\033[0m"
    cd "$PROJECT_ROOT/web"

    # 检查依赖
    [ -d "node_modules" ] || npm install

    echo "  -> Vite 启动在 http://localhost:5173"

    # 前台启动（Ctrl+C 停止）
    npm run dev &
    FRONTEND_PID=$!
    echo "  -> 前端 PID: $FRONTEND_PID"
fi

echo -e "\n\033[36m========================================\033[0m"
echo -e "\033[36m  启动完成!\033[0m"
echo -e "\033[32m  前端: http://localhost:5173\033[0m"
echo -e "\033[32m  后端: http://localhost:8000\033[0m"
echo -e "\033[32m  API文档: http://localhost:8000/docs\033[0m"
echo -e "\033[36m========================================\033[0m"
echo -e "\n\033[90m提示: 在 .env 中配置 LLM_API_KEY 后即可使用 Agent 功能\033[0m"

# 等待后台进程
if [[ -n "${FRONTEND_PID:-}" ]] || [[ -n "${BACKEND_PID:-}" ]]; then
    wait
fi
