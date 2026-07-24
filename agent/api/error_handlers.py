"""全局异常处理程序。

将所有异常统一转换为接口规范要求的格式：
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "人类可读的错误描述",
            "details": {}
        }
    }

对齐：开发任务与接口规范.md 1.1 节通用约定。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.auth_errors import password_policy_violation
from security.passwords import PasswordPolicyViolation

logger = logging.getLogger(__name__)


# ── HTTP 状态码 → 错误码映射 ─────────────────────────────────

_HTTP_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _build_error_body(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    status_code: int = 500,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """构建统一的错误响应 JSON。"""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
        headers=headers,
    )


def _is_password_policy_validation_error(error: dict[str, Any]) -> bool:
    """Identify the typed password-policy failure retained by Pydantic."""
    context = error.get("ctx")
    return isinstance(context, dict) and isinstance(
        context.get("error"), PasswordPolicyViolation
    )


# ── 处理器注册 ────────────────────────────────────────────────


def register_error_handlers(app) -> None:
    """在 FastAPI 实例上注册所有异常处理器。"""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """处理 HTTPException（含 FastAPI 的 HTTPException）。

        将 FastAPI 默认的 {"detail": "..."} 格式转换为统一错误格式。
        """
        code = _HTTP_CODE_MAP.get(exc.status_code, "HTTP_ERROR")

        # 提取消息：可能是字符串或 dict（如 deps.py 中 parse_project_id 的 422）
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            # 已经是统一格式，直接返回
            return JSONResponse(
                status_code=exc.status_code,
                content=detail,
                headers=exc.headers,
            )

        if isinstance(detail, str):
            message = detail
        elif isinstance(detail, list):
            # FastAPI 默认的验证错误列表格式
            message = "; ".join(
                d.get("msg", str(d)) if isinstance(d, dict) else str(d)
                for d in detail
            )
        else:
            message = str(detail)

        logger.warning(
            "HTTP error | status=%d code=%s path=%s message=%s",
            exc.status_code, code, request.url.path, message[:200],
        )

        return _build_error_body(
            code=code,
            message=message,
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """处理 Pydantic 请求体验证错误。

        将字段级别的验证错误展开为结构化 details。
        """
        errors = exc.errors()
        if any(_is_password_policy_validation_error(error) for error in errors):
            policy_error = password_policy_violation()
            return JSONResponse(
                status_code=policy_error.status_code,
                content=policy_error.detail,
                headers=policy_error.headers,
            )

        field_errors: dict[str, list[str]] = {}
        for error in errors:
            loc = ".".join(str(l) for l in error["loc"])
            msg = error.get("msg", "Unknown error")
            field_errors.setdefault(loc, []).append(msg)

        message = "请求参数校验失败"
        if field_errors:
            first_loc = next(iter(field_errors))
            first_msg = field_errors[first_loc][0]
            message = f"参数校验失败: {first_loc} — {first_msg}"

        logger.warning(
            "Validation error | path=%s errors=%d first=%s",
            request.url.path, len(exc.errors()), message[:200],
        )

        return _build_error_body(
            code="VALIDATION_ERROR",
            message=message,
            details={"field_errors": field_errors},
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """处理未预期的异常，统一返回 500。

        生产环境不应暴露 traceback，仅记录日志。
        """
        logger.exception(
            "Unhandled exception | path=%s method=%s type=%s",
            request.url.path, request.method, type(exc).__name__,
        )

        return _build_error_body(
            code="INTERNAL_ERROR",
            message="服务器内部错误，请稍后重试",
            status_code=500,
        )
