from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.banking.importers.categorizer import infer_category
from app.infrastructure.database.banking.models import BankAccountModel, TransactionModel


async def backfill_nubank_categories(session: AsyncSession) -> int:
    """Set category on Nubank transactions that currently have none. Returns updated count."""
    rows = (
        await session.execute(
            select(TransactionModel.id, TransactionModel.description)
            .join(BankAccountModel)
            .where(BankAccountModel.bank == "nubank")
            .where(TransactionModel.category.is_(None))
        )
    ).all()

    updated = 0
    for row in rows:
        category = infer_category(row.description)
        if category:
            await session.execute(
                update(TransactionModel)
                .where(TransactionModel.id == row.id)
                .values(category=category)
            )
            updated += 1

    await session.commit()
    return updated
