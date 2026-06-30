from __future__ import annotations

import uuid

from opentelemetry import trace

from app.application.item.dtos import ItemDTO, UpdateItemDTO, item_to_dto
from app.domain.item.repository import IItemRepository
from app.shared.exceptions import NotFoundError

tracer = trace.get_tracer(__name__)


class UpdateItemUseCase:
    def __init__(self, repo: IItemRepository) -> None:
        self._repo = repo

    async def execute(self, item_id: uuid.UUID, dto: UpdateItemDTO) -> ItemDTO:
        with tracer.start_as_current_span("item.update") as span:
            span.set_attribute("item.id", str(item_id))
            item = await self._repo.get_by_id(item_id)
            if item is None:
                raise NotFoundError(f"Item {item_id} not found")
            item.update(name=dto.name, description=dto.description)
            updated = await self._repo.update(item)
            return item_to_dto(updated)
