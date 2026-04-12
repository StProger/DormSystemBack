"""HTTP request/response logging middleware with correlation ID."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import trace_id_ctx, user_id_ctx

logger = logging.getLogger("dorm.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Trace ID: from header or generate new
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        trace_id_token = trace_id_ctx.set(trace_id)

        # Best-effort user_id extraction from JWT
        user_id = "-"
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                import jwt
                from app.core.config import get_settings
                settings = get_settings()
                payload = jwt.decode(auth[7:], settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
                user_id = payload.get("sub", "-")
            except Exception:
                pass
        user_id_token = user_id_ctx.set(user_id)

        client_ip = request.client.host if request.client else "-"

        logger.info(
            "request_started",
            extra={
                "event": "request_started",
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_ip,
            },
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            if response.status_code == 200:
                logger.info(
                    "request_completed",
                    extra={
                        "event": "request_completed",
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "client_ip": client_ip,
                    },
                )
            else:
                logger.error(
                    "request_completed",
                    extra={
                        "event": "request_completed",
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "client_ip": client_ip,
                    },
                )
            response.headers["X-Trace-Id"] = trace_id
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "request_failed",
                extra={
                    "event": "request_failed",
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                },
                exc_info=exc,
            )
            raise
        finally:
            trace_id_ctx.reset(trace_id_token)
            user_id_ctx.reset(user_id_token)
