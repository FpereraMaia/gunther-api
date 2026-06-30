"""Security headers middleware.

Adds defensive HTTP headers to every response:
  X-Frame-Options         — prevents clickjacking (DENY)
  X-Content-Type-Options  — prevents MIME-type sniffing (nosniff)
  X-XSS-Protection        — disable legacy browser filter (0 = use CSP instead)
  Referrer-Policy         — limits referrer exposure
  Permissions-Policy      — disables unused powerful features
  Strict-Transport-Security (production only) — enforces HTTPS
  Content-Security-Policy (production only)   — restrictive default; adjust for
                                                 your frontend's CDN origins

These headers are harmless in development and critical in production.
The Swagger UI (/docs, /redoc) is excluded from CSP so it keeps working locally.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.shared.config import settings

_ALWAYS_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    ),
}

_PRODUCTION_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "Content-Security-Policy": "default-src 'self'; object-src 'none'; base-uri 'self'",
}

_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        for name, value in _ALWAYS_HEADERS.items():
            response.headers[name] = value

        if settings.is_production and request.url.path not in _DOCS_PATHS:
            for name, value in _PRODUCTION_HEADERS.items():
                response.headers[name] = value

        return response
