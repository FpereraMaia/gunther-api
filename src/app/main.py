"""FastAPI application factory and lifespan.

Composition root — the only place where all layers are wired together.
Import order matters: telemetry must be initialised before other imports
so instrumentation patches are applied at startup.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.shared.config import settings
from app.shared.exceptions import (
    ApplicationError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)

_PROBLEM_DETAIL_BASE = f"/{settings.otel_service_name}/errors"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan — runs startup logic, yields (app serves requests), then teardown.

    Startup order:
      1. Telemetry (OTel + Sentry) — must be first so instrumentation patches apply
      2. Structured logging — after OTel so the OTLP log exporter is wired
      3. Database connection pool
    """
    # ── Phase 3: telemetry ────────────────────────────────────────────────────
    from app.infrastructure.telemetry.logging import setup_logging
    from app.infrastructure.telemetry.otel import setup_telemetry
    from app.infrastructure.telemetry.sentry import setup_sentry

    setup_telemetry(settings)  # must be first — patches instrumentation hooks
    setup_logging(settings)
    setup_sentry(settings)

    # ── Phase 5: database ─────────────────────────────────────────────────────
    from sqlalchemy import text

    from app.infrastructure.database.session import engine

    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))  # fail fast if DB is unreachable

    logger.info("service.startup", extra={"service": settings.otel_service_name})

    yield  # ← app serves requests here

    # ── Teardown — drain connections before exit ───────────────────────────────
    await engine.dispose()
    from app.infrastructure.cache.redis import close_redis

    await close_redis()
    logger.info("service.shutdown", extra={"service": settings.otel_service_name})


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title="Gunther API",
        description="test",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    _register_middleware(app)
    _register_exception_handlers(app)
    _register_routers(app)

    return app


def _register_middleware(app: FastAPI) -> None:
    # Starlette executes middleware in REVERSE registration order.
    # Desired execution order (first→last):
    #   CorrelationID → AccessLog → SecurityHeaders → CORS → handler
    # So registration order is the reverse of that:
    from app.presentation.middleware.correlation import CorrelationIDMiddleware
    from app.presentation.middleware.logging import AccessLogMiddleware
    from app.presentation.middleware.security import SecurityHeadersMiddleware

    app.add_middleware(  # registered 1st → runs last (closest to handler)
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)  # registered 2nd
    app.add_middleware(AccessLogMiddleware)  # registered 3rd
    from app.presentation.middleware.rate_limit import setup_rate_limiting

    setup_rate_limiting(app)
    app.add_middleware(CorrelationIDMiddleware)  # registered last → runs first


def _register_routers(app: FastAPI) -> None:
    from app.infrastructure.telemetry.otel import make_metrics_asgi_app
    from app.presentation.api.v1.health import router as health_router

    app.include_router(health_router)
    app.mount("/metrics", make_metrics_asgi_app())
    from app.presentation.api.v1.auth.router import router as auth_router

    app.include_router(auth_router)

    from app.presentation.api.v1.finance.router import router as finance_router

    app.include_router(finance_router)

    from app.presentation.api.v1.banking.router import router as banking_router

    app.include_router(banking_router)


def _register_exception_handlers(app: FastAPI) -> None:
    """Map domain/application exceptions to RFC 7807 Problem Details responses."""

    def _problem(
        type_slug: str,
        title: str,
        status_code: int,
        detail: str,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={
                "type": f"{_PROBLEM_DETAIL_BASE}/{type_slug}",
                "title": title,
                "status": status_code,
                "detail": detail,
            },
        )

    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return _problem("not-found", "Not Found", status.HTTP_404_NOT_FOUND, str(exc))

    @app.exception_handler(ConflictError)
    async def _conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return _problem("conflict", "Conflict", status.HTTP_409_CONFLICT, str(exc))

    @app.exception_handler(AuthenticationError)
    async def _unauthenticated(request: Request, exc: AuthenticationError) -> JSONResponse:
        return _problem("unauthenticated", "Unauthorized", status.HTTP_401_UNAUTHORIZED, str(exc))

    @app.exception_handler(AuthorizationError)
    async def _forbidden(request: Request, exc: AuthorizationError) -> JSONResponse:
        return _problem("forbidden", "Forbidden", status.HTTP_403_FORBIDDEN, str(exc))

    @app.exception_handler(ValidationError)
    async def _validation(request: Request, exc: ValidationError) -> JSONResponse:
        return _problem(
            "validation-error",
            "Unprocessable Entity",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            str(exc),
        )

    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError) -> JSONResponse:
        return _problem(
            "domain-error",
            "Business Rule Violation",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            str(exc),
        )

    @app.exception_handler(ApplicationError)
    async def _application(request: Request, exc: ApplicationError) -> JSONResponse:
        return _problem(
            "application-error", "Application Error", status.HTTP_400_BAD_REQUEST, str(exc)
        )


app = create_app()
