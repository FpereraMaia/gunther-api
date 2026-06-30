"""In-memory fake repository implementations for use-case unit tests.

Each fake satisfies the domain Protocol without any database dependency.
Use these in unit tests so the test suite stays fast and isolated:

    from tests.fakes import InMemoryItemRepository
    from app.application.item.use_cases.create_item import CreateItemUseCase

    async def test_create_item():
        repo = InMemoryItemRepository()
        result = await CreateItemUseCase(repo=repo).execute(...)
        assert result.name == ...
"""
from __future__ import annotations

import uuid

from app.domain.item.entity import Item
from app.shared.exceptions import NotFoundError


class InMemoryItemRepository:
    """Fully in-memory IItemRepository — no SQLAlchemy, no DB."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, Item] = {}

    async def add(self, item: Item) -> Item:
        self._store[item.id] = item
        return item

    async def get_by_id(self, item_id: uuid.UUID) -> Item | None:
        return self._store.get(item_id)

    async def list_all(self, offset: int, limit: int) -> tuple[list[Item], int]:
        all_items = list(self._store.values())
        return all_items[offset : offset + limit], len(all_items)

    async def update(self, item: Item) -> Item:
        if item.id not in self._store:
            raise NotFoundError(f"Item {item.id} not found")
        self._store[item.id] = item
        return item

    async def delete(self, item_id: uuid.UUID) -> None:
        self._store.pop(item_id, None)
