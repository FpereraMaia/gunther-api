"""Auth router — POST /api/v1/auth/token.

Standard OAuth2 password flow. The login use case is injected via
_get_login_use_case(); wire the concrete User repository there once the
User domain is scaffolded.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.application.auth.dtos import LoginDTO, TokenDTO
from app.application.auth.use_cases.login import LoginUseCase
from app.shared.exceptions import AuthenticationError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _get_login_use_case() -> LoginUseCase:
    """
    Dependency factory — replace this body after scaffolding the User domain:

        from app.infrastructure.database.user.repository import UserRepository
        from app.infrastructure.database.session import get_db_session

        # (inject session via Depends — see other routers for the pattern)
        return LoginUseCase(user_repo=UserRepository(session))
    """
    raise NotImplementedError(
        "Wire LoginUseCase to the User repository. Run: octopus scaffold domain gunther_api user"
    )


@router.post(
    "/token",
    response_model=TokenDTO,
    summary="OAuth2 password login",
    description="Returns a Bearer JWT for use in the Authorization header.",
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    use_case: Annotated[LoginUseCase, Depends(_get_login_use_case)],
) -> TokenDTO:
    try:
        return await use_case.execute(LoginDTO(username=form.username, password=form.password))
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
