"""/health/live and /health/ready endpoints.

live  — liveness: the process is up (always 200 if the endpoint responds)
ready — readiness: all dependencies are reachable (DB, Redis)
         Used by the platform load balancer and Docker HEALTHCHECK.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db_session
from app.infrastructure.cache.redis import get_redis

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: str = "ok"


@router.get(
    "",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe (bare /health)",
)
@router.get(
    "/live",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
)
async def liveness() -> LivenessResponse:
    """Returns 200 as long as the process is alive."""
    return LivenessResponse()


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Dependency unavailable"}},
)
async def readiness(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JSONResponse:
    """Returns 200 when all dependencies are healthy, 503 otherwise."""
    checks: dict[str, str] = {}

    # ── Database ──────────────────────────────────────────────────────────────
    try:
        await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    # ── Redis ─────────────────────────────────────────────────────────────────
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ok" if all_ok else "degraded", **checks},
    )
