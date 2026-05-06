from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.infrastructure.log.logging_config import get_logger

logger = get_logger("access")

_SKIP_PATHS = frozenset({"/health", "/api/docs", "/api/redoc", "/api/openapi.json"})


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request with method, path, status code, and duration.

    Skips health-check and documentation paths to reduce noise.
    Logs a WARNING when the request exceeds SLOW_REQUEST_THRESHOLD_MS.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        request_id = getattr(request.state, "request_id", "-")
        log_line = (
            f'{request.method} {request.url.path} '
            f'→ {response.status_code} '
            f'[{duration_ms:.1f}ms] rid={request_id}'
        )

        if duration_ms > settings.SLOW_REQUEST_THRESHOLD_MS:
            logger.warning("SLOW %s", log_line)
        else:
            logger.info(log_line)

        return response
