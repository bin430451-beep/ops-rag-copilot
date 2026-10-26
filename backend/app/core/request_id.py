"""request_id 全链路中间件 + 访问日志（可观测性）。"""
import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

access_log = logging.getLogger("access")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求生成/透传 X-Request-ID，并输出结构化访问日志。

    添加顺序：应最后注册（Starlette 后注册者先执行），保证覆盖全部请求。
    """

    async def dispatch(self, request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.request_id = rid
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            access_log.exception(
                "method=%s path=%s status=500 request_id=%s",
                request.method, request.url.path, rid,
            )
            raise
        cost_ms = (time.monotonic() - start) * 1000
        response.headers["X-Request-ID"] = rid
        access_log.info(
            "method=%s path=%s status=%d cost_ms=%.1f request_id=%s",
            request.method, request.url.path, response.status_code, cost_ms, rid,
        )
        return response
