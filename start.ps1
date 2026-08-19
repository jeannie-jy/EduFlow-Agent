# EduFlow-Agent 一键启动脚本 (Windows PowerShell)
# 用法: .\start.ps1 [-Infra] [-Backend] [-Frontend] [-All]
param(
    [switch]$Infra,
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$All
)

# 默认启动全部
if (-not ($Infra -or $Backend -or $Frontend)) {
    $All = $true
}

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  EduFlow-Agent 启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ── 1. 检查 .env ──────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Write-Host "[!] 未找到 .env 文件，从 .env.example 复制..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[!] 请编辑 .env 填入 API Key，然后重新运行" -ForegroundColor Yellow
    Write-Host "    LLM_API_KEY=your-deepseek-api-key" -ForegroundColor Yellow
    Write-Host "    EMBEDDING_API_KEY=your-openai-api-key" -ForegroundColor Yellow
    exit 1
}

# ── 2. 启动基础设施（Docker）────────────────────────────────
if ($All -or $Infra) {
    Write-Host "`n[1/3] 启动基础设施 (PostgreSQL + Redis + MinIO)..." -ForegroundColor Green
    docker compose up -d postgres redis minio
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Docker 启动失败，请确认 Docker Desktop 已运行" -ForegroundColor Red
        exit 1
    }
    Write-Host "  -> PostgreSQL: localhost:5432" -ForegroundColor Gray
    Write-Host "  -> Redis: localhost:6379" -ForegroundColor Gray
    Write-Host "  -> MinIO: localhost:9000 (Console: :9001)" -ForegroundColor Gray

    # 等待 PostgreSQL 就绪
    Write-Host "  等待 PostgreSQL 就绪..." -ForegroundColor Gray
    $retry = 0
    do {
        Start-Sleep -Seconds 2
        $retry++
        $healthy = docker compose exec -T postgres pg_isready -U agent -d eduflow 2>$null
    } while ($LASTEXITCODE -ne 0 -and $retry -lt 15)

    if ($retry -ge 15) {
        Write-Host "[!] PostgreSQL 启动超时" -ForegroundColor Red
        exit 1
    }
    Write-Host "  -> PostgreSQL 已就绪" -ForegroundColor Gray
}

# ── 3. 启动后端 ──────────────────────────────────────────
if ($All -or $Backend) {
    Write-Host "`n[2/3] 启动后端 (FastAPI)..." -ForegroundColor Green
    Set-Location "$projectRoot\agent"

    # 检查虚拟环境
    if (Test-Path ".venv\Scripts\Activate.ps1") {
        Write-Host "  -> 激活虚拟环境 .venv" -ForegroundColor Gray
        . .venv\Scripts\Activate.ps1
    }

    # 检查依赖
    if (-not (Test-Path ".venv\Lib\site-packages\fastapi")) {
        Write-Host "  -> 安装 Python 依赖..." -ForegroundColor Gray
        pip install -r requirements.txt
    }

    Write-Host "  -> FastAPI 启动在 http://localhost:8000" -ForegroundColor Gray
    Write-Host "  -> API 文档: http://localhost:8000/docs" -ForegroundColor Gray

    # 在新的 PowerShell 窗口启动 uvicorn
    Start-Process powershell -ArgumentList @"
-NoExit -Command `
    Set-Location '$projectRoot\agent'; `
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir agents --reload-dir api --reload-dir adapters --reload-dir db --reload-dir generators --reload-dir plugins --reload-dir schema --reload-dir services --reload-dir tools --reload-dir alembic --reload-dir scripts --reload-dir main.py --log-level info
"@
}

# ── 4. 启动前端 ──────────────────────────────────────────
if ($All -or $Frontend) {
    Write-Host "`n[3/3] 启动前端 (Vite)..." -ForegroundColor Green
    Set-Location "$projectRoot\web"

    # 检查依赖
    if (-not (Test-Path "node_modules")) {
        Write-Host "  -> 安装 Node 依赖..." -ForegroundColor Gray
        npm install
    }

    Write-Host "  -> Vite 启动在 http://localhost:5173" -ForegroundColor Gray

    # 在新的 PowerShell 窗口启动 vite
    Start-Process powershell -ArgumentList @"
-NoExit -Command `
    Set-Location '$projectRoot\web'; `
    npm run dev
"@
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  启动完成!" -ForegroundColor Cyan
Write-Host "  前端: http://localhost:5173" -ForegroundColor Green
Write-Host "  后端: http://localhost:8000" -ForegroundColor Green
Write-Host "  API文档: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n提示: 在 .env 中配置 LLM_API_KEY 后即可使用 Agent 功能" -ForegroundColor Gray
