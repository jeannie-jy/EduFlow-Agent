"""异步数据库连接管理。

使用 SQLAlchemy 2.0 async engine + asyncpg 驱动。
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import get_settings

logger = logging.getLogger(__name__)

# ── Engine & Session ──────────────────────────────────────────


def create_engine():
    """创建异步 SQLAlchemy engine。"""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


engine = create_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：获取异步数据库会话（读写操作使用）。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_readonly_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：只读数据库会话（避免不必要的 commit 开销）。"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
