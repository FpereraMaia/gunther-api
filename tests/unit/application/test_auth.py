"""Unit tests for JWT token creation/verification and password hashing.

These tests run without any database or HTTP stack.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.auth.dtos import LoginDTO, TokenDTO
from app.application.auth.use_cases.login import LoginUseCase
from app.infrastructure.security.jwt import create_access_token, decode_token
from app.infrastructure.security.passwords import hash_password, verify_password
from app.shared.exceptions import AuthenticationError

# ── JWT ───────────────────────────────────────────────────────────────────────


def test_create_and_decode_token() -> None:
    token = create_access_token(subject="user-123")
    payload = decode_token(token)
    assert payload.sub == "user-123"
    assert payload.exp > datetime.now(UTC)
    assert payload.jti != ""


def test_decode_invalid_token_raises() -> None:
    with pytest.raises(AuthenticationError):
        decode_token("not.a.token")


def test_decode_tampered_token_raises() -> None:
    token = create_access_token(subject="user-123")
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(AuthenticationError):
        decode_token(tampered)


def test_token_has_unique_jti() -> None:
    t1 = create_access_token("u1")
    t2 = create_access_token("u1")
    assert decode_token(t1).jti != decode_token(t2).jti


def test_extra_claims_included() -> None:
    token = create_access_token("u1", extra_claims={"role": "admin"})
    import jwt as _jwt

    from app.shared.config import settings

    raw = _jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert raw["role"] == "admin"


# ── Passwords ─────────────────────────────────────────────────────────────────


def test_hash_and_verify() -> None:
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)


def test_wrong_password_rejected() -> None:
    hashed = hash_password("correct")
    assert not verify_password("wrong", hashed)


def test_hash_is_not_plain_text() -> None:
    plain = "mysecret"
    assert hash_password(plain) != plain


def test_same_plain_produces_different_hashes() -> None:
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2  # bcrypt uses random salts


# ── LoginUseCase ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_user() -> MagicMock:
    user = MagicMock()
    user.id = "user-uuid-1234"
    user.password_hash = hash_password("correct_password")
    return user


@pytest.fixture
def mock_repo(mock_user: MagicMock) -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_username.return_value = mock_user
    return repo


async def test_login_success(mock_repo: AsyncMock, mock_user: MagicMock) -> None:
    use_case = LoginUseCase(user_repo=mock_repo)
    result = await use_case.execute(
        LoginDTO(username="alice", password="correct_password")  # pragma: allowlist secret
    )
    assert isinstance(result, TokenDTO)
    assert result.token_type == "bearer"
    payload = decode_token(result.access_token)
    assert payload.sub == str(mock_user.id)


async def test_login_user_not_found_raises(mock_repo: AsyncMock) -> None:
    mock_repo.find_by_username.return_value = None
    use_case = LoginUseCase(user_repo=mock_repo)
    with pytest.raises(AuthenticationError):
        await use_case.execute(
            LoginDTO(username="ghost", password="any")  # pragma: allowlist secret
        )


async def test_login_wrong_password_raises(mock_repo: AsyncMock) -> None:
    use_case = LoginUseCase(user_repo=mock_repo)
    with pytest.raises(AuthenticationError):
        await use_case.execute(
            LoginDTO(username="alice", password="wrong_password")  # pragma: allowlist secret
        )
