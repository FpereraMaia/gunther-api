"""SQLAlchemy declarative base and reusable ORM mixins.

All ORM models inherit from Base. Domain entities are pure Python dataclasses
with no SQLAlchemy dependency — see domain/<entity>/entities.py for those.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    """UUID v4 primary key — avoids integer ID leakage and enables sharding."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        insert_default=uuid.uuid4,
    )


class TimestampMixin:
    """created_at / updated_at managed by the database, not the application."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
