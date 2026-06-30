"""Shared fixtures for integration tests under `tests/integration/`."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.banking.models import (
    BankAccountModel,
    ImportJobModel,
    TransactionModel,
)


@pytest.fixture
async def banking_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """A session whose commits are real, not auto-rolled-back like `db_session`.

    Needed for tests that seed data through one connection and then read it
    back through another — e.g. seeding via `BankingRepository` and then
    querying through `test_client`, which opens its own engine/connection (see
    `tests/conftest.py::test_client`). Data inserted in a still-open,
    uncommitted transaction on one connection is invisible to a different
    connection, so the seed step must actually commit. Cleans up by
    truncating the banking tables afterward instead of relying on rollback.
    """
    async with session_factory() as session:
        yield session
        await session.execute(delete(TransactionModel))
        await session.execute(delete(ImportJobModel))
        await session.execute(delete(BankAccountModel))
        await session.commit()
