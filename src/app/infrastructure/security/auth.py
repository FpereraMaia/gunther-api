"""Authentik ForwardAuth integration — read user context from proxy-injected headers.

In production, Traefik's ForwardAuth middleware calls Authentik before every
request. Authentik injects the authenticated user's info as request headers.
This module reads those headers and exposes them as FastAPI dependencies.

In development (devcontainer / local uvicorn), set DEV_USER_UID in .env to
bypass header requirement without touching production code paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from app.shared.config import settings


@dataclass
class UserContext:
    uid: str
    username: str
    email: str
    groups: list[str] = field(default_factory=list)


def get_user(request: Request) -> UserContext:
    """Dependency — extract authenticated user from Authentik proxy headers."""
    uid = request.headers.get("X-authentik-uid", "")

    # Dev bypass: set DEV_USER_UID in .env (never set in production)
    if not uid and settings.dev_user_uid:
        return UserContext(
            uid=settings.dev_user_uid,
            username=settings.dev_user_username,
            email=settings.dev_user_email,
            groups=settings.dev_user_groups,
        )

    if not uid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    raw_groups = request.headers.get("X-authentik-groups", "")
    groups = [g for g in raw_groups.split("|") if g]

    return UserContext(
        uid=uid,
        username=request.headers.get("X-authentik-username", ""),
        email=request.headers.get("X-authentik-email", ""),
        groups=groups,
    )


def require_group(group: str) -> Any:
    """Dependency factory — raise 403 if the authenticated user lacks the group."""

    def _check(user: UserContext = Depends(get_user)) -> UserContext:
        if group not in user.groups:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Group '{group}' required",
            )
        return user

    return Depends(_check)
