"""API 层通用依赖与工具函数。"""

from __future__ import annotations

import uuid
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth_errors import access_token_invalid, account_disabled
from db.database import async_session_factory, get_readonly_session
from db.models import User
from security.tokens import AccessTokenError, decode_access_token

logger = logging.getLogger(__name__)

_access_token_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(_access_token_scheme)
    ],
    session: Annotated[AsyncSession, Depends(get_readonly_session)],
) -> User:
    """Resolve the active user represented by a bearer access token."""
    if credentials is None:
        raise access_token_invalid()

    try:
        claims = decode_access_token(credentials.credentials)
    except AccessTokenError:
        raise access_token_invalid()

    user = await session.get(User, claims.user_id)
    if user is None:
        raise access_token_invalid()
    if not user.is_active:
        raise account_disabled()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_stream_current_user_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(_access_token_scheme)
    ],
) -> uuid.UUID:
    """Resolve a streaming principal in a session closed before streaming begins."""
    if credentials is None:
        raise access_token_invalid()

    try:
        claims = decode_access_token(credentials.credentials)
    except AccessTokenError:
        raise access_token_invalid()

    async with async_session_factory() as session:
        user = await session.get(User, claims.user_id)
        if user is None:
            raise access_token_invalid()
        if not user.is_active:
            raise account_disabled()
        return user.id


StreamCurrentUserId = Annotated[uuid.UUID, Depends(get_stream_current_user_id)]


def parse_project_id(project_id: str) -> uuid.UUID:
    """安全地将 project_id 字符串解析为 UUID，非法格式返回 422。"""
    try:
        return uuid.UUID(project_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "INVALID_UUID",
                    "message": f"无效的项目 ID 格式: {project_id}",
                }
            },
        )


def safe_project_uuid(project_id: str) -> uuid.UUID | None:
    """尝试解析 UUID，失败返回 None（不抛异常）。"""
    try:
        return uuid.UUID(project_id)
    except (ValueError, AttributeError):
        return None
