"""EduFlow-Agent 后端入口。

FastAPI 应用，负责：
- Agent 编排流程的 HTTP 暴露
- SSE 流式推送生成进度
- 项目/帧/参数/导出 CRUD
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings

logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期：启动时配置日志，关闭时释放资源。"""
    settings = get_settings()
    _setup_logging(settings)
    logger.info("EduFlow-Agent 启动 | log_level=%s format=%s", settings.log_level, settings.log_format)

    # 注册模块生成器（Phase A: 模块化生成器架构）
    try:
        import generators.mindmap_generator   # noqa: F401 — 触发 register_generator
        import generators.card_generator      # noqa: F401
        import generators.frames_generator    # noqa: F401
        import generators.video_generator     # noqa: F401
        import generators.quiz_generator      # noqa: F401
        import generators.comparison_generator  # noqa: F401
        from generators.registry import list_generators
        logger.info("已注册 %d 个模块生成器", len(list_generators()))
    except Exception as exc:
        logger.warning("模块生成器注册失败: %s", exc)

    # TODO: 初始化 DB 连接池、Redis 客户端
    yield

    # 关闭 Agent checkpointer 连接
    try:
        from agents.graph import close_checkpointer
        await close_checkpointer()
    except Exception as exc:
        logger.warning("关闭 checkpointer 异常: %s", exc)

    # TODO: 关闭 DB 连接池、Redis 客户端
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
    app = FastAPI(
        title="EduFlow-Agent API",
        description="面向计算机科学教育的自主 Agent 教学推演系统",
        version="0.1.0",
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
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
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
    """健康检查端点。"""
    return {"status": "ok", "version": "0.1.0"}
