"""Alembic async migration environment.

Uses async_engine_from_config so migrations run through the same asyncpg driver
as the application. DATABASE_URL is read from Pydantic Settings (→ .env file).
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.infrastructure.database.base import Base
import app.infrastructure.database.models  # noqa: F401 — registers all models with Base.metadata
from app.shared.config import settings

alembic_config = context.config
alembic_config.set_main_option("sqlalchemy.url", settings.database_url)

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    engine_section = alembic_config.get_section(alembic_config.config_ini_section) or {}
    connectable = async_engine_from_config(engine_section, prefix="sqlalchemy.")
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    url = alembic_config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
