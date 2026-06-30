"""Async SQLAlchemy engine, session factory, and dependency injection helpers.

Patterns:
  get_db_session() — FastAPI dependency for read/mixed endpoints;
                     yields an AsyncSession scoped to the request lifetime.
  unit_of_work()   — context manager for use cases that need a committed
                     transaction; commits on success, rolls back on exception.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.shared.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=False,
    pool_pre_ping=True,
)

_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an AsyncSession scoped to the HTTP request."""
    async with _session_factory() as session:
        yield session


@asynccontextmanager
async def unit_of_work() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for use cases that must commit as an atomic unit.

    Usage:
        async with unit_of_work() as session:
            await repo.save(entity, session=session)
        # committed here, or rolled back if an exception was raised
    """
    async with _session_factory() as session:
        async with session.begin():
            yield session
