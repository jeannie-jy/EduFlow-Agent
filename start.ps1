# EduFlow-Agent 一键启动脚本 (Windows PowerShell)
# 用法: .\start.ps1 [-Infra] [-Backend] [-Frontend] [-Video] [-All]
param(
    [switch]$Infra,
    [switch]$Backend,
    [switch]$Frontend,
    [switch]$Video,
    [switch]$All
)

# 默认启动全部
if (-not ($Infra -or $Backend -or $Frontend -or $Video)) {
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
if ($All -or $Infra -or $Video) {
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

# ── 3. 启动隔离视频服务（可选）──────────────────────────
if ($Video) {
    Write-Host "`n[2/4] 启动视频 Worker + 隔离渲染沙箱..." -ForegroundColor Green
    docker compose --profile video up -d --build render-worker render-sandbox
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] 视频服务启动失败，请检查 Docker 构建输出" -ForegroundColor Red
        exit 1
    }
    Start-Sleep -Seconds 2
    $videoServices = docker compose --profile video ps --status running --services
    if (-not ($videoServices -contains "render-worker") -or -not ($videoServices -contains "render-sandbox")) {
        Write-Host "[!] 视频 Worker 或沙箱未保持运行，请执行 docker compose --profile video logs render-worker render-sandbox" -ForegroundColor Red
        exit 1
    }
    Write-Host "  -> 视频任务准备器与无网络渲染沙箱已运行" -ForegroundColor Gray
}

# ── 4. 启动后端 ──────────────────────────────────────────
if ($All -or $Backend -or $Video) {
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
        pip install -r requirements.lock.txt
    }

    Write-Host "  -> FastAPI 启动在 http://localhost:8000" -ForegroundColor Gray
    Write-Host "  -> API 文档: http://localhost:8000/docs" -ForegroundColor Gray

    Write-Host "  -> 检查并升级数据库迁移..." -ForegroundColor Gray
    python -m scripts.adopt_legacy_database --apply
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] 数据库迁移失败，后端未启动；请检查上方迁移诊断" -ForegroundColor Red
        exit 1
    }

    # 视频模式只对新后端进程启用队列与 MinIO；常规开发仍保持安全默认值。
    $videoEnvironmentBackup = @{}
    if ($Video) {
        foreach ($name in @("MANIM_EXECUTION_MODE", "ARTIFACT_STORE_BACKEND", "MINIO_ENDPOINT")) {
            $videoEnvironmentBackup[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
        }
        $env:MANIM_EXECUTION_MODE = "queue"
        $env:ARTIFACT_STORE_BACKEND = "minio"
        $env:MINIO_ENDPOINT = "localhost:9000"
        Write-Host "  -> API 已启用视频排队模式，产物写入 MinIO" -ForegroundColor Gray
    }

    # 在新的 PowerShell 窗口启动 uvicorn
    Start-Process powershell -ArgumentList @"
-NoExit -Command `
    Set-Location '$projectRoot\agent'; `
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir agents --reload-dir api --reload-dir adapters --reload-dir db --reload-dir generators --reload-dir plugins --reload-dir schema --reload-dir services --reload-dir tools --reload-dir alembic --reload-dir scripts --reload-dir main.py --log-level info
"@

    if ($Video) {
        foreach ($name in $videoEnvironmentBackup.Keys) {
            [Environment]::SetEnvironmentVariable($name, $videoEnvironmentBackup[$name], "Process")
        }
    }
}

# ── 5. 启动前端 ──────────────────────────────────────────
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
if ($Video) {
    Write-Host "  视频: Worker + 隔离沙箱已启用" -ForegroundColor Green
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n提示: 在 .env 中配置 LLM_API_KEY 后即可使用 Agent 功能" -ForegroundColor Gray
