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
    """应用生命周期：启动时连接基础设施，关闭时释放资源。"""
    settings = get_settings()
    logger.info("EduFlow-Agent 启动中 | log_level=%s", settings.log_level)

    # TODO: 初始化 DB 连接池、Redis 客户端
    yield

    # TODO: 关闭 DB 连接池、Redis 客户端
    logger.info("EduFlow-Agent 已关闭")


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
