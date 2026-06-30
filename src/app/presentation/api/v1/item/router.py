"""Item router — CRUD endpoints for the example Item domain.

Route protection:
  POST / PATCH / DELETE require authentication when include_auth=y.
  GET routes are always public.

Background task:
  After a successful POST, a notify_example task is enqueued when
  include_background_tasks=y. Replace with your real notification task.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.application.item.dtos import CreateItemDTO, UpdateItemDTO
from app.application.item.use_cases.create_item import CreateItemUseCase
from app.application.item.use_cases.delete_item import DeleteItemUseCase
from app.application.item.use_cases.get_item import GetItemUseCase
from app.application.item.use_cases.list_items import ListItemsUseCase
from app.application.item.use_cases.update_item import UpdateItemUseCase
from app.presentation.api.v1.item.dependencies import (
    get_create_use_case,
    get_delete_use_case,
    get_get_use_case,
    get_list_use_case,
    get_update_use_case,
)
from app.presentation.api.v1.item.schemas import (
    CreateItemRequest,
    ItemResponse,
    PaginatedItemsResponse,
    UpdateItemRequest,
)
from app.infrastructure.security.auth import UserContext as TokenPayload
from app.infrastructure.security.auth import get_user as get_current_user

_write_deps = [Depends(get_current_user)]

router = APIRouter(prefix="/api/v1/items", tags=["items"])


@router.post(
    "/",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=_write_deps,
)
async def create_item(
    body: CreateItemRequest,
    use_case: Annotated[CreateItemUseCase, Depends(get_create_use_case)],
) -> ItemResponse:
    dto = await use_case.execute(CreateItemDTO(name=body.name, description=body.description))
    from arq import create_pool
    from app.application.tasks.example import notify_example
    from app.shared.correlation import get as get_correlation_id
    from app.worker import WorkerSettings

    redis = await create_pool(WorkerSettings.redis_settings)
    await redis.enqueue_job(
        notify_example,
        resource_id=str(dto.id),
        _correlation_id=get_correlation_id(),
    )
    return ItemResponse(
        id=dto.id,
        name=dto.name,
        description=dto.description,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )


@router.get("/", response_model=PaginatedItemsResponse)
async def list_items(
    use_case: Annotated[ListItemsUseCase, Depends(get_list_use_case)],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> PaginatedItemsResponse:
    result = await use_case.execute(offset=offset, limit=limit)
    return PaginatedItemsResponse(
        items=[
            ItemResponse(
                id=i.id,
                name=i.name,
                description=i.description,
                created_at=i.created_at,
                updated_at=i.updated_at,
            )
            for i in result.items
        ],
        total=result.total,
        offset=result.offset,
        limit=result.limit,
    )


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: uuid.UUID,
    use_case: Annotated[GetItemUseCase, Depends(get_get_use_case)],
) -> ItemResponse:
    dto = await use_case.execute(item_id)
    return ItemResponse(
        id=dto.id,
        name=dto.name,
        description=dto.description,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )


@router.patch(
    "/{item_id}",
    response_model=ItemResponse,
    dependencies=_write_deps,
)
async def update_item(
    item_id: uuid.UUID,
    body: UpdateItemRequest,
    use_case: Annotated[UpdateItemUseCase, Depends(get_update_use_case)],
) -> ItemResponse:
    dto = await use_case.execute(item_id, UpdateItemDTO(name=body.name, description=body.description))
    return ItemResponse(
        id=dto.id,
        name=dto.name,
        description=dto.description,
        created_at=dto.created_at,
        updated_at=dto.updated_at,
    )


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=_write_deps,
)
async def delete_item(
    item_id: uuid.UUID,
    use_case: Annotated[DeleteItemUseCase, Depends(get_delete_use_case)],
) -> None:
    await use_case.execute(item_id)
