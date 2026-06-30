from __future__ import annotations

from opentelemetry import trace

from app.application.item.dtos import PaginatedItemsDTO, item_to_dto
from app.domain.item.repository import IItemRepository

tracer = trace.get_tracer(__name__)

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


class ListItemsUseCase:
    def __init__(self, repo: IItemRepository) -> None:
        self._repo = repo

    async def execute(self, offset: int = 0, limit: int = _DEFAULT_LIMIT) -> PaginatedItemsDTO:
        limit = min(limit, _MAX_LIMIT)
        with tracer.start_as_current_span("item.list") as span:
            span.set_attribute("query.offset", offset)
            span.set_attribute("query.limit", limit)
            items, total = await self._repo.list_all(offset=offset, limit=limit)
            span.set_attribute("result.total", total)
            return PaginatedItemsDTO(
                items=[item_to_dto(i) for i in items],
                total=total,
                offset=offset,
                limit=limit,
            )
