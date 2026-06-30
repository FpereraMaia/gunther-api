"""Root conftest — fixtures shared across the entire test suite.

Database strategy:
  A single PostgreSQL testcontainer is started once per session (not per test).
  Each test that uses `db_session` gets its own transaction that is rolled back
  after the test, so tests are isolated without restarting the container.

Fixtures available to all tests:
  test_client      — sync  TestClient with get_db_session overridden
  async_client     — async AsyncClient with get_db_session overridden
  db_session       — async AsyncSession (rolled back after each test)
  item_factory     — factory-boy ItemFactory class (no DB required)
  fake_item_repo   — fresh InMemoryItemRepository for use-case unit tests
  redis_url        — Redis testcontainer URL (session-scoped)
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.database.base import Base
import app.infrastructure.database.models  # noqa: F401 — ensures all tables are in Base.metadata
from app.infrastructure.database.session import get_db_session
from app.main import app
from tests.factories import ItemFactory
from tests.fakes import InMemoryItemRepository


# ── Postgres testcontainer ─────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Start a PostgreSQL 16 container once per test session."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as container:
        yield container.get_connection_url().replace(
            "postgresql://", "postgresql+asyncpg://"
        )


@pytest.fixture(scope="session")
async def db_engine(postgres_url: str) -> AsyncIterator[Any]:
    """Create the async engine and apply the full schema from metadata."""
    engine = create_async_engine(postgres_url, echo=False, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def session_factory(db_engine: Any) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


# ── Per-test DB session (auto-rolled-back) ─────────────────────────────────────

@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Async session rolled back after every test — zero cleanup needed."""
    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


# ── HTTP test clients ──────────────────────────────────────────────────────────

def _make_session_override(
    factory: async_sessionmaker[AsyncSession],
) -> Any:
    async def _override() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    return _override


@pytest.fixture
def test_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[TestClient]:
    """Sync TestClient with database dependency overridden to use the test DB."""
    app.dependency_overrides[get_db_session] = _make_session_override(session_factory)
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    """Async client with database dependency overridden to use the test DB."""
    app.dependency_overrides[get_db_session] = _make_session_override(session_factory)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ── Factory and fake-repo fixtures ─────────────────────────────────────────────

@pytest.fixture
def item_factory() -> type[ItemFactory]:
    """Return the ItemFactory class — call it to build domain entities."""
    return ItemFactory


@pytest.fixture
def fake_item_repo() -> InMemoryItemRepository:
    """Fresh in-memory Item repository — isolated per test, no DB required."""
    return InMemoryItemRepository()

# ── Redis testcontainer ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    """Start a Redis 7 container and patch settings so the app uses it."""
    from testcontainers.redis import RedisContainer

    from app.shared.config import settings

    with RedisContainer("redis:7-alpine") as container:
        url = f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}"
        # Patch the module-level settings singleton so TestClient / AsyncClient
        # routes that touch slowapi or cache hit the testcontainer, not localhost.
        original = settings.redis_url
        settings.redis_url = url  # type: ignore[misc]
        yield url
        settings.redis_url = original  # type: ignore[misc]
