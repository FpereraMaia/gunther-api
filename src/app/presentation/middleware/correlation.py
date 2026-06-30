"""Correlation ID middleware.

On every inbound request:
  1. Reads X-Correlation-ID header, or generates a fresh UUID4
  2. Stores it in a ContextVar (readable by structlog on any log call)
  3. Propagates it via OTel baggage (httpx instrumentation forwards it downstream)
  4. Echoes it back in the response X-Correlation-ID header

Clients can pass their own ID to trace a flow across multiple services.
If absent, a new one is generated per request.
"""
from __future__ import annotations

from opentelemetry import baggage, context
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.shared import correlation

HEADER = "X-Correlation-ID"


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cid = request.headers.get(HEADER) or correlation.generate()
        token = correlation.set_id(cid)

        # Propagate via OTel baggage so outbound httpx calls carry the ID
        ctx = baggage.set_baggage("correlation_id", cid)
        otel_token = context.attach(ctx)
        try:
            response = await call_next(request)
        finally:
            context.detach(otel_token)
            correlation.reset(token)

        response.headers[HEADER] = cid
        return response
