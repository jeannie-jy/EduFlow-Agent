"""API 中间件。

- Request ID 注入（X-Request-ID → logging context）
- 请求耗时日志
"""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("api")

_UUID_SEGMENT = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
_INTEGER_SEGMENT = re.compile(r"^\d+$")


def _bounded_route_label(request: Request) -> str:
    """Return a stable metric label even when routing has not completed yet."""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if template:
        return str(template)
    segments = []
    for segment in request.url.path.split("/"):
        if _UUID_SEGMENT.fullmatch(segment):
            segments.append("{id}")
        elif _INTEGER_SEGMENT.fullmatch(segment):
            segments.append("{number}")
        else:
            segments.append(segment[:80])
    return "/".join(segments)[:240]


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 request_id 并记录耗时。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        from services.telemetry import record_http_request, request_id_var

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        context_token = request_id_var.set(request_id)
        start = time.perf_counter()
        request.state.request_id = request_id

        try:
            response = await self._rate_limited_response(request, request_id)
            if response is None:
                response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            logger.error(
                "request failed | method=%s path=%s request_id=%s",
                request.method,
                request.url.path,
                request_id,
            )
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            record_http_request(
                method=request.method,
                route=_bounded_route_label(request),
                status_code=status_code,
                duration_ms=elapsed_ms,
            )
            request_id_var.reset(context_token)

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request completed | method=%s path=%s status=%d duration_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            status_code,
            elapsed_ms,
            request_id,
        )
        return response

    async def _rate_limited_response(
        self, request: Request, request_id: str
    ) -> Response | None:
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        if request.url.path in {"/api/auth/login", "/api/auth/register"}:
            return None  # These endpoints have stricter, dedicated limits.

        from config import get_settings
        from services.rate_limit import check_rate_limit

        settings = get_settings()
        if not settings.auth_required:
            return None
        costly_markers = ("/generate", "/regenerate", "/recompute", "/export/")
        costly = any(marker in request.url.path for marker in costly_markers)
        scope = "generation" if costly else "write"
        limit = (
            settings.api_generation_rate_limit
            if costly
            else settings.api_write_rate_limit
        )
        window = (
            settings.api_generation_rate_window_seconds
            if costly
            else settings.api_write_rate_window_seconds
        )
        identifier = request.cookies.get("eduflow_session") or (
            request.client.host if request.client else "unknown"
        )
        retry_after = await check_rate_limit(
            scope, identifier, limit=limit, window_seconds=window
        )
        if retry_after is None:
            return None
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Too many requests",
                    "request_id": request_id,
                }
            },
            headers={"Retry-After": str(retry_after)},
        )
