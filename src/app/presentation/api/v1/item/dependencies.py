"""Wiring layer — connects use cases to their concrete repository implementations.

This is the only file that imports from both application/ and infrastructure/.
All other files respect the dependency rule (outer layers depend on inner layers only).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.item.use_cases.create_item import CreateItemUseCase
from app.application.item.use_cases.delete_item import DeleteItemUseCase
from app.application.item.use_cases.get_item import GetItemUseCase
from app.application.item.use_cases.list_items import ListItemsUseCase
from app.application.item.use_cases.update_item import UpdateItemUseCase
from app.infrastructure.database.item.repository import SQLAlchemyItemRepository
from app.infrastructure.database.session import get_db_session


def _item_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SQLAlchemyItemRepository:
    return SQLAlchemyItemRepository(session)


_Repo = Annotated[SQLAlchemyItemRepository, Depends(_item_repo)]


def get_create_use_case(repo: _Repo) -> CreateItemUseCase:
    return CreateItemUseCase(repo=repo)


def get_get_use_case(repo: _Repo) -> GetItemUseCase:
    return GetItemUseCase(repo=repo)


def get_list_use_case(repo: _Repo) -> ListItemsUseCase:
    return ListItemsUseCase(repo=repo)


def get_update_use_case(repo: _Repo) -> UpdateItemUseCase:
    return UpdateItemUseCase(repo=repo)


def get_delete_use_case(repo: _Repo) -> DeleteItemUseCase:
    return DeleteItemUseCase(repo=repo)
