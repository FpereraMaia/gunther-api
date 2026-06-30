"""Rate limiting via slowapi (Redis-backed).

This module is only included when include_redis=y.
slowapi integrates with FastAPI at the application level rather than as a
BaseHTTPMiddleware — it hooks into FastAPI's exception handling instead.

Setup (called from main.py):

    from app.presentation.middleware.rate_limit import setup_rate_limiting
    setup_rate_limiting(app)

Per-route usage:

    from fastapi import Request
    from app.presentation.middleware.rate_limit import limiter

    @router.get("/my-endpoint")
    @limiter.limit("100/minute")
    async def my_endpoint(request: Request) -> ...:
        ...

    # Different limits per user tier:
    @router.post("/items/")
    @limiter.limit("10/minute", key_func=lambda r: r.headers.get("X-API-Key", r.client.host))
    async def create_item(request: Request, ...) -> ...:
        ...

Rate limit key:
  Default key is the client IP address (get_remote_address).
  Override key_func per route for API-key or user-based limits.

Redis backend:
  Uses the same Redis URL as the rest of the application.
  Counters expire automatically — no manual cleanup needed.
"""
from __future__ import annotations

from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.shared.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    default_limits=["1000/hour"],
)


def setup_rate_limiting(app: FastAPI) -> None:
    """Install slowapi into the FastAPI app.

    Call once in _register_middleware() in main.py:

        from app.presentation.middleware.rate_limit import setup_rate_limiting
        setup_rate_limiting(app)
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
