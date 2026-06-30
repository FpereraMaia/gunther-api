"""Unit tests for Item use cases — no database, no HTTP.

All five use cases are tested against InMemoryItemRepository so tests
run in milliseconds without Docker. The factory-boy factories produce
realistic domain objects for setup.
"""
from __future__ import annotations

import uuid

import pytest

from app.application.item.dtos import CreateItemDTO, UpdateItemDTO
from app.application.item.use_cases.create_item import CreateItemUseCase
from app.application.item.use_cases.delete_item import DeleteItemUseCase
from app.application.item.use_cases.get_item import GetItemUseCase
from app.application.item.use_cases.list_items import ListItemsUseCase
from app.application.item.use_cases.update_item import UpdateItemUseCase
from app.shared.exceptions import NotFoundError
from tests.factories import ItemFactory
from tests.fakes import InMemoryItemRepository


@pytest.fixture
def repo() -> InMemoryItemRepository:
    return InMemoryItemRepository()


# ── CreateItemUseCase ──────────────────────────────────────────────────────────


async def test_create_returns_item_with_generated_id(repo: InMemoryItemRepository) -> None:
    dto = await CreateItemUseCase(repo=repo).execute(
        CreateItemDTO(name="Widget", description="A nice widget")
    )
    assert dto.name == "Widget"
    assert dto.description == "A nice widget"
    assert dto.id is not None


async def test_create_empty_description_defaults_to_empty_string(
    repo: InMemoryItemRepository,
) -> None:
    dto = await CreateItemUseCase(repo=repo).execute(CreateItemDTO(name="Bare"))
    assert dto.description == ""


async def test_create_persists_item_in_repo(repo: InMemoryItemRepository) -> None:
    created = await CreateItemUseCase(repo=repo).execute(CreateItemDTO(name="Persist Me"))
    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.name == "Persist Me"


# ── GetItemUseCase ─────────────────────────────────────────────────────────────


async def test_get_existing_item(repo: InMemoryItemRepository) -> None:
    item = ItemFactory()
    await repo.add(item)
    dto = await GetItemUseCase(repo=repo).execute(item.id)
    assert dto.id == item.id
    assert dto.name == item.name


async def test_get_nonexistent_raises_not_found(repo: InMemoryItemRepository) -> None:
    with pytest.raises(NotFoundError):
        await GetItemUseCase(repo=repo).execute(uuid.uuid4())


# ── ListItemsUseCase ───────────────────────────────────────────────────────────


async def test_list_returns_all_items(repo: InMemoryItemRepository) -> None:
    for item in ItemFactory.build_batch(5):
        await repo.add(item)
    result = await ListItemsUseCase(repo=repo).execute()
    assert result.total == 5
    assert len(result.items) == 5


async def test_list_pagination_offset(repo: InMemoryItemRepository) -> None:
    for item in ItemFactory.build_batch(10):
        await repo.add(item)
    result = await ListItemsUseCase(repo=repo).execute(offset=7, limit=5)
    assert result.total == 10
    assert len(result.items) == 3   # only 3 items after offset 7


async def test_list_limit_capped_at_100(repo: InMemoryItemRepository) -> None:
    for item in ItemFactory.build_batch(5):
        await repo.add(item)
    result = await ListItemsUseCase(repo=repo).execute(limit=999)
    assert result.limit == 100   # clamped internally


async def test_list_empty_repo(repo: InMemoryItemRepository) -> None:
    result = await ListItemsUseCase(repo=repo).execute()
    assert result.total == 0
    assert result.items == []


# ── UpdateItemUseCase ──────────────────────────────────────────────────────────


async def test_update_name(repo: InMemoryItemRepository) -> None:
    item = ItemFactory(name="Old")
    await repo.add(item)
    dto = await UpdateItemUseCase(repo=repo).execute(
        item.id, UpdateItemDTO(name="New")
    )
    assert dto.name == "New"


async def test_update_description_only(repo: InMemoryItemRepository) -> None:
    item = ItemFactory(name="Fixed", description="old")
    await repo.add(item)
    dto = await UpdateItemUseCase(repo=repo).execute(
        item.id, UpdateItemDTO(description="updated")
    )
    assert dto.name == "Fixed"   # unchanged
    assert dto.description == "updated"


async def test_update_nonexistent_raises_not_found(repo: InMemoryItemRepository) -> None:
    with pytest.raises(NotFoundError):
        await UpdateItemUseCase(repo=repo).execute(
            uuid.uuid4(), UpdateItemDTO(name="Ghost")
        )


# ── DeleteItemUseCase ──────────────────────────────────────────────────────────


async def test_delete_removes_item(repo: InMemoryItemRepository) -> None:
    item = ItemFactory()
    await repo.add(item)
    await DeleteItemUseCase(repo=repo).execute(item.id)
    assert await repo.get_by_id(item.id) is None


async def test_delete_nonexistent_raises_not_found(repo: InMemoryItemRepository) -> None:
    with pytest.raises(NotFoundError):
        await DeleteItemUseCase(repo=repo).execute(uuid.uuid4())
