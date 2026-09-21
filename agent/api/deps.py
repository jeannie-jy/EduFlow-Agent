"""API 层通用依赖与工具函数。"""

from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException

logger = logging.getLogger(__name__)


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
        ) from None


def safe_project_uuid(project_id: str) -> uuid.UUID | None:
    """尝试解析 UUID，失败返回 None（不抛异常）。"""
    try:
        return uuid.UUID(project_id)
    except (ValueError, AttributeError):
        return None


def ensure_project_access(project, user) -> None:
    """Fail closed for authenticated cross-tenant project access."""
    if user is None or getattr(user, "role", None) == "admin":
        return
    if project is None or str(getattr(project, "owner_id", "")) != str(user.id):
        raise HTTPException(status_code=404, detail="Project not found")
