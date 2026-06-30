"""Auth domain value objects — pure Python, no framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TokenPayload:
    """Decoded JWT payload — passed to protected route handlers via Depends."""

    sub: str  # subject — typically a stringified entity UUID
    exp: datetime  # expiry timestamp (UTC)
    jti: str  # JWT ID — reserved for token revocation
