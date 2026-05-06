from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # Strict-Transport-Security is only meaningful over HTTPS; the load balancer
    # or reverse proxy should set HSTS. We skip it here to avoid issues in dev.
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security response headers to every non-streaming response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        # SSE responses are streaming — avoid touching their headers.
        if "text/event-stream" not in response.headers.get("content-type", ""):
            for header, value in _SECURITY_HEADERS.items():
                response.headers.setdefault(header, value)
        return response
