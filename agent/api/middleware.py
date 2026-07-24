"""API 中间件。

- Request ID 注入（X-Request-ID → logging context）
- 请求耗时日志
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 request_id 并记录耗时。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            status_code = 500
            logger.error(
                "request failed | method=%s path=%s request_id=%s error_type=%s message=%s",
                request.method,
                request.url.path,
                request_id,
                type(exc).__name__,
                "request processing failed",
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request completed | method=%s path=%s status=%d duration_ms=%.1f request_id=%s",
            request.method, request.url.path, status_code,
            elapsed_ms, request_id,
        )
        return response
