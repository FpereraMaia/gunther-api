from __future__ import annotations

import uuid

from opentelemetry import trace

from app.domain.item.repository import IItemRepository
from app.shared.exceptions import NotFoundError

tracer = trace.get_tracer(__name__)


class DeleteItemUseCase:
    def __init__(self, repo: IItemRepository) -> None:
        self._repo = repo

    async def execute(self, item_id: uuid.UUID) -> None:
        with tracer.start_as_current_span("item.delete") as span:
            span.set_attribute("item.id", str(item_id))
            item = await self._repo.get_by_id(item_id)
            if item is None:
                raise NotFoundError(f"Item {item_id} not found")
            await self._repo.delete(item_id)
