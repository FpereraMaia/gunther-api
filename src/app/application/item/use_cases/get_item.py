from __future__ import annotations

import uuid

from opentelemetry import trace

from app.application.item.dtos import ItemDTO, item_to_dto
from app.domain.item.repository import IItemRepository
from app.shared.exceptions import NotFoundError

tracer = trace.get_tracer(__name__)


class GetItemUseCase:
    def __init__(self, repo: IItemRepository) -> None:
        self._repo = repo

    async def execute(self, item_id: uuid.UUID) -> ItemDTO:
        with tracer.start_as_current_span("item.get") as span:
            span.set_attribute("item.id", str(item_id))
            item = await self._repo.get_by_id(item_id)
            if item is None:
                raise NotFoundError(f"Item {item_id} not found")
            return item_to_dto(item)
