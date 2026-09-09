"""EduFlow-Agent 后端入口。

FastAPI 应用，负责：
- Agent 编排流程的 HTTP 暴露
- SSE 流式推送生成进度
- 项目/帧/参数/导出 CRUD
"""

from __future__ import annotations

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db.database import get_readonly_session

logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期：启动时配置日志，关闭时释放资源。"""
    settings = get_settings()
    _setup_logging(settings)
    logger.info("EduFlow-Agent 启动 | log_level=%s format=%s", settings.log_level, settings.log_format)

    # Do not start background tasks against an unversioned or partially migrated
    # database. This turns legacy-volume drift into one actionable startup error.
    from services.schema_guard import assert_database_schema_current

    await assert_database_schema_current()

    # 注册模块生成器（Phase A: 模块化生成器架构）
    try:
        import generators.mindmap_generator   # noqa: F401 — 触发 register_generator
        import generators.card_generator      # noqa: F401
        import generators.frames_generator    # noqa: F401
        import generators.video_generator     # noqa: F401
        import generators.quiz_generator      # noqa: F401
        import generators.comparison_generator  # noqa: F401
        import generators.misconception_generator  # noqa: F401
        import generators.pathway_generator  # noqa: F401
        import generators.sandbox_generator  # noqa: F401
        import generators.interactive_demo_generator  # noqa: F401
        from generators.registry import list_generators
        logger.info("已注册 %d 个模块生成器", len(list_generators()))
    except Exception as exc:
        logger.warning("模块生成器注册失败: %s", exc)

    from services.material_retention import run_material_retention

    retention_stop = asyncio.Event()
    retention_task = asyncio.create_task(run_material_retention(retention_stop))

    # DB engine、Redis 与 LLM client 均按首次使用惰性建立连接。
    yield

    retention_stop.set()
    retention_task.cancel()
    try:
        await retention_task
    except asyncio.CancelledError:
        pass

    # 关闭 Agent checkpointer 连接
    try:
        from agents.graph import close_checkpointer
        await close_checkpointer()
    except Exception as exc:
        logger.warning("关闭 checkpointer 异常: %s", exc)

    try:
        from api.export import close_export_resources
        from db.database import close_database

        await close_export_resources()
        await close_database()
    except Exception as exc:
        logger.warning("关闭数据库或 Redis 资源异常: %s", exc)

    logger.info("EduFlow-Agent 已关闭")


def _setup_logging(settings) -> None:
    """配置根日志记录器，支持 text / json 格式。"""
    if settings.log_format == "json":
        import sys
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","message":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))
        logging.getLogger().handlers = [handler]
    logging.getLogger().setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))


# ── App ───────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """工厂函数：创建并配置 FastAPI 实例。"""
    settings = get_settings()
    app = FastAPI(
        title="EduFlow-Agent API",
        description="面向计算机科学教育的自主 Agent 教学推演系统",
        version=settings.app_version,
        lifespan=lifespan,
    )

    # CORS — MVP 阶段允许本地开发来源
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
    )

    # 请求日志与 request_id 追踪
    from api.middleware import RequestLoggingMiddleware
    app.add_middleware(RequestLoggingMiddleware)

    # 全局异常处理程序（统一错误响应格式）
    from api.error_handlers import register_error_handlers
    register_error_handlers(app)

    # 注册路由
    from api.router import api_router
    app.include_router(api_router, prefix="/api")

    return app


app = create_app()


# ── Health ────────────────────────────────────────────────────


@app.get("/api/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Process liveness check; it intentionally performs no network I/O."""
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version}


async def readiness_checks() -> dict[str, str]:
    """Probe dependencies needed to accept generation and export work."""
    from sqlalchemy import text

    checks: dict[str, str] = {}
    try:
        from db.database import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.warning("readiness database check failed: %s", exc)
        checks["database"] = "unavailable"

    try:
        from api.export import _get_redis

        redis_client = await _get_redis()
        if redis_client is None:
            raise ConnectionError("redis client unavailable")
        pong = await __import__("asyncio").to_thread(redis_client.ping)
        checks["redis"] = "ok" if pong else "unavailable"
    except Exception as exc:
        logger.warning("readiness redis check failed: %s", exc)
        checks["redis"] = "unavailable"

    try:
        from services.artifact_store import get_artifact_store

        await get_artifact_store().ready()
        checks["artifact_store"] = "ok"
    except Exception as exc:
        logger.warning("readiness artifact store check failed: %s", exc)
        checks["artifact_store"] = "unavailable"
    return checks


@app.get("/api/ready", tags=["system"])
async def readiness_check(response: Response) -> dict[str, object]:
    checks = await readiness_checks()
    ready = all(value == "ok" for value in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "not_ready", "checks": checks}


@app.get("/api/metrics", tags=["system"])
async def process_metrics(
    session: AsyncSession = Depends(get_readonly_session),
) -> dict[str, object]:
    """Process telemetry plus cross-process aggregates from durable state."""
    from services.operational_metrics import operational_metrics_snapshot
    from services.telemetry import telemetry_snapshot

    snapshot = telemetry_snapshot()
    snapshot["operational"] = await operational_metrics_snapshot(session)
    return snapshot


@app.get("/api/metrics/prometheus", tags=["system"], response_class=PlainTextResponse)
async def prometheus_metrics(
    session: AsyncSession = Depends(get_readonly_session),
) -> str:
    from services.operational_metrics import operational_metrics_snapshot, prometheus_text

    return prometheus_text(await operational_metrics_snapshot(session))
