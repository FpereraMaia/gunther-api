"""Auth application DTOs — data flowing into and out of auth use cases."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoginDTO:
    username: str
    password: str


@dataclass(frozen=True)
class TokenDTO:
    access_token: str
    token_type: str = "bearer"  # noqa: S105 -- OAuth2 token type, not a secret
