"""JWT token creation, verification, and FastAPI dependency.

Algorithm: HS256 (HMAC-SHA256). Secret loaded from settings.jwt_secret_key.
The get_current_user dependency is used in any route that requires authentication:

    @router.get("/me")
    async def me(user: Annotated[TokenPayload, Depends(get_current_user)]) -> ...:
        ...  # user.sub is the authenticated entity's ID
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.domain.auth.value_objects import TokenPayload
from app.shared.config import settings
from app.shared.exceptions import AuthenticationError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Sign and return a JWT access token for the given subject."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
        **(extra_claims or {}),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT. Raises AuthenticationError on failure."""
    try:
        raw = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(
            sub=raw["sub"],
            exp=datetime.fromtimestamp(raw["exp"], tz=timezone.utc),
            jti=raw.get("jti", ""),
        )
    except (JWTError, KeyError) as exc:
        raise AuthenticationError("Invalid or expired token") from exc


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> TokenPayload:
    """FastAPI dependency — decode Bearer token and return the token payload."""
    return decode_token(token)
