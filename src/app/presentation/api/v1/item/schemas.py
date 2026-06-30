from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=5000)


class UpdateItemRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)


class ItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    created_at: datetime | None
    updated_at: datetime | None


class PaginatedItemsResponse(BaseModel):
    items: list[ItemResponse]
    total: int
    offset: int
    limit: int
