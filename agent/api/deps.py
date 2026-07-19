"""API 层通用依赖与工具函数。"""

from __future__ import annotations

import uuid
import logging

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
        )


def safe_project_uuid(project_id: str) -> uuid.UUID | None:
    """尝试解析 UUID，失败返回 None（不抛异常）。"""
    try:
        return uuid.UUID(project_id)
    except (ValueError, AttributeError):
        return None
