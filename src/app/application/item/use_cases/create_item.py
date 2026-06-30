from __future__ import annotations

from opentelemetry import trace

from app.application.item.dtos import CreateItemDTO, ItemDTO, item_to_dto
from app.domain.item.entity import Item
from app.domain.item.repository import IItemRepository

tracer = trace.get_tracer(__name__)


class CreateItemUseCase:
    def __init__(self, repo: IItemRepository) -> None:
        self._repo = repo

    async def execute(self, dto: CreateItemDTO) -> ItemDTO:
        with tracer.start_as_current_span("item.create") as span:
            item = Item(name=dto.name, description=dto.description)
            span.set_attribute("item.name", dto.name)
            created = await self._repo.add(item)
            span.set_attribute("item.id", str(created.id))
            return item_to_dto(created)
