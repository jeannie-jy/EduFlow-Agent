[CmdletBinding()]
param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$testsPath = Join-Path $repoRoot "agent\tests"
$composePath = Join-Path $repoRoot "docker-compose.yml"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required to verify the M1 video export milestone."
}

docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is not running or the Docker engine is unavailable."
}

# Compose requires explicit local-only secrets even when this script only builds
# the video images. These values are intentionally disposable and are never used
# outside the validation process.
$env:DB_PASSWORD = "m1-validation-db-password"
$env:MINIO_USER = "m1-validation-access"
$env:MINIO_PASSWORD = "m1-validation-secret-password"
$env:CREDENTIAL_KEK_B64 = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="

try {
    Push-Location $repoRoot

    docker compose --profile video config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Video Compose configuration is invalid." }

    if (-not $SkipBuild) {
        docker compose --profile video build render-worker render-sandbox
        if ($LASTEXITCODE -ne 0) { throw "Video image build failed." }
    }

    docker run --rm --network none `
        --mount "type=bind,source=$testsPath,target=/app/tests,readonly" `
        --mount "type=bind,source=$composePath,target=/docker-compose.yml,readonly" `
        eduflow-agent-render-worker:latest `
        python -m pytest tests/test_export_worker.py -q
    if ($LASTEXITCODE -ne 0) { throw "Export worker/sandbox tests failed." }

    docker run --rm --network none `
        --tmpfs /tmp:rw,size=1g,mode=1777 `
        --mount "type=bind,source=$testsPath,target=/app/tests,readonly" `
        eduflow-agent-render-sandbox:latest `
        python -m pytest tests/test_manim_render_smoke.py -m render -q
    if ($LASTEXITCODE -ne 0) { throw "Real Manim/FFmpeg smoke tests failed." }

    Write-Host "M1 video export verification passed." -ForegroundColor Green
}
finally {
    Pop-Location
    Remove-Item Env:DB_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:MINIO_USER -ErrorAction SilentlyContinue
    Remove-Item Env:MINIO_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:CREDENTIAL_KEK_B64 -ErrorAction SilentlyContinue
}
