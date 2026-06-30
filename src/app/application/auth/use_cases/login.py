"""LoginUseCase — verify credentials and issue a JWT access token.

The use case depends on IUserAuthRepository (a structural Protocol), not a
concrete SQLAlchemy class. The concrete implementation is provided in
presentation/dependencies.py once the User domain is scaffolded:

    octopus scaffold domain gunther_api user

Then wire it:
    # infrastructure/database/user/repository.py — implements IUserAuthRepository
    # presentation/dependencies.py — return LoginUseCase(user_repo=UserRepository(session))
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.application.auth.dtos import LoginDTO, TokenDTO
from app.infrastructure.security.jwt import create_access_token
from app.infrastructure.security.passwords import verify_password
from app.shared.exceptions import AuthenticationError


@runtime_checkable
class IUserAuthRepository(Protocol):
    """Minimal user repository interface required by LoginUseCase."""

    async def find_by_username(self, username: str) -> Any | None:
        """Return an object with .id and .password_hash, or None."""
        ...


class LoginUseCase:
    def __init__(self, user_repo: IUserAuthRepository) -> None:
        self._repo = user_repo

    async def execute(self, dto: LoginDTO) -> TokenDTO:
        user = await self._repo.find_by_username(dto.username)
        if not user or not verify_password(dto.password, user.password_hash):
            # Same error for both cases — avoids username enumeration
            raise AuthenticationError("Invalid credentials")

        token = create_access_token(subject=str(user.id))
        return TokenDTO(access_token=token)
