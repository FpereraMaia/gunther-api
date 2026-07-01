from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.banking.importers.categorizer import infer_category
from app.infrastructure.database.banking.repository import BankingRepository


async def backfill_nubank_categories(session: AsyncSession) -> int:
    """Set category on Nubank transactions that currently have none. Returns updated count."""
    repo = BankingRepository(session)
    rows = await repo.list_uncategorized_transactions(bank="nubank")

    updated = 0
    for row_id, description in rows:
        category = infer_category(description)
        if category:
            await repo.update_transaction_category(row_id, category)
            updated += 1

    await session.commit()
    return updated
