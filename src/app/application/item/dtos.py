"""Item application DTOs and the domain→DTO mapper used by all use cases."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.item.entity import Item


@dataclass(frozen=True)
class CreateItemDTO:
    name: str
    description: str = ""


@dataclass(frozen=True)
class UpdateItemDTO:
    name: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class ItemDTO:
    id: uuid.UUID
    name: str
    description: str
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class PaginatedItemsDTO:
    items: list[ItemDTO]
    total: int
    offset: int
    limit: int


def item_to_dto(item: Item) -> ItemDTO:
    return ItemDTO(
        id=item.id,
        name=item.name,
        description=item.description,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
