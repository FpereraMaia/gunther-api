"""Access log middleware — structured log line per request.

Emits one log record per request with: method, path, status, duration_ms,
correlation_id. Written AFTER the response is returned so status is final.

Placement in the middleware stack (Starlette reverse-registration order):
  This middleware is registered after SecurityHeadersMiddleware and before
  CorrelationIDMiddleware, so it runs after CorrelationID is set but before
  SecurityHeaders adds response headers — ensuring the log captures the
  real application status, not a modified version.
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.shared import correlation

logger = logging.getLogger(__name__)

_SKIP_PATHS = frozenset({"/metrics", "/health", "/health/live", "/health/ready", "/healthz"})


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        logger.info(
            "http.access",
            extra={
                "http_method": request.method,
                "http_path": request.url.path,
                "http_status": response.status_code,
                "duration_ms": duration_ms,
                "correlation_id": correlation.get(),
                "client_ip": request.client.host if request.client else None,
            },
        )
        return response
