from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.item.entity import Item
from app.infrastructure.database.item.model import ItemModel
from app.shared.exceptions import NotFoundError


class SQLAlchemyItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: Item) -> Item:
        model = ItemModel(id=item.id, name=item.name, description=item.description)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, item_id: uuid.UUID) -> Item | None:
        result = await self._session.execute(
            select(ItemModel).where(ItemModel.id == item_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_all(self, offset: int, limit: int) -> tuple[list[Item], int]:
        total = (
            await self._session.execute(select(func.count()).select_from(ItemModel))
        ).scalar_one()
        rows = (
            await self._session.execute(
                select(ItemModel)
                .order_by(ItemModel.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars()
        return [self._to_entity(m) for m in rows], total

    async def update(self, item: Item) -> Item:
        model = await self._session.get(ItemModel, item.id)
        if model is None:
            raise NotFoundError(f"Item {item.id} not found")
        model.name = item.name
        model.description = item.description
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, item_id: uuid.UUID) -> None:
        model = await self._session.get(ItemModel, item_id)
        if model is not None:
            await self._session.delete(model)

    @staticmethod
    def _to_entity(model: ItemModel) -> Item:
        return Item(
            id=model.id,
            name=model.name,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
