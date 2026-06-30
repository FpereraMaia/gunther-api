"""Integration tests for `backfill_nubank_categories` against a real Postgres testcontainer.

Uses `banking_session` (real commits, no explicit `session.begin()` wrapper)
since the use case calls `session.commit()` itself — that would conflict with
`db_session`'s own explicit transaction (see `tests/integration/conftest.py`).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.banking.use_cases.backfill_categories import backfill_nubank_categories
from app.infrastructure.database.banking.models import TransactionModel
from app.infrastructure.database.banking.repository import BankingRepository


async def _seed_transaction(
    session: AsyncSession,
    bank: str,
    description: str,
    card_last4: str = "1234",
) -> uuid.UUID:
    repo = BankingRepository(session)
    account = await repo.get_or_create_account(bank, card_last4, "Felipe")
    job = await repo.create_import_job(
        bank_account_id=account.id,
        source_type="gmail",
        source_ref=f"seed-{uuid.uuid4()}",
        billing_date=date(2026, 6, 1),
        row_count=1,
    )
    row_id = uuid.uuid4()
    await repo.bulk_insert_transactions(
        [
            {
                "id": row_id,
                "import_job_id": job.id,
                "bank_account_id": account.id,
                "date": date(2026, 6, 1),
                "description": description,
                "category": None,
                "amount_brl": 10.00,
                "amount_usd": None,
                "exchange_rate": None,
                "installment_current": None,
                "installment_total": None,
                "row_hash": str(row_id),
                "raw": {},
            }
        ]
    )
    return row_id


async def test_backfill_sets_category_on_matching_nubank_transaction(
    banking_session: AsyncSession,
) -> None:
    row_id = await _seed_transaction(banking_session, "nubank", "Uber Trip")

    updated = await backfill_nubank_categories(banking_session)

    assert updated == 1
    category = (
        await banking_session.execute(
            select(TransactionModel.category).where(TransactionModel.id == row_id)
        )
    ).scalar_one()
    assert category == "Transporte"


async def test_backfill_does_not_touch_other_banks(banking_session: AsyncSession) -> None:
    c6_row_id = await _seed_transaction(banking_session, "c6", "Uber Trip", card_last4="5678")

    updated = await backfill_nubank_categories(banking_session)

    assert updated == 0
    category = (
        await banking_session.execute(
            select(TransactionModel.category).where(TransactionModel.id == c6_row_id)
        )
    ).scalar_one()
    assert category is None


async def test_backfill_leaves_unmatched_description_uncategorized(
    banking_session: AsyncSession,
) -> None:
    row_id = await _seed_transaction(banking_session, "nubank", "Completely Unrecognizable Inc")

    updated = await backfill_nubank_categories(banking_session)

    assert updated == 0
    category = (
        await banking_session.execute(
            select(TransactionModel.category).where(TransactionModel.id == row_id)
        )
    ).scalar_one()
    assert category is None


async def test_backfill_skips_rows_that_already_have_a_category(
    banking_session: AsyncSession,
) -> None:
    repo = BankingRepository(banking_session)
    account = await repo.get_or_create_account("nubank", "1234", "Felipe")
    job = await repo.create_import_job(
        bank_account_id=account.id,
        source_type="gmail",
        source_ref="seed-already-categorized",
        billing_date=date(2026, 6, 1),
        row_count=1,
    )
    row_id = uuid.uuid4()
    await repo.bulk_insert_transactions(
        [
            {
                "id": row_id,
                "import_job_id": job.id,
                "bank_account_id": account.id,
                "date": date(2026, 6, 1),
                "description": "Uber Trip",
                "category": "Already Set",
                "amount_brl": 10.00,
                "amount_usd": None,
                "exchange_rate": None,
                "installment_current": None,
                "installment_total": None,
                "row_hash": str(row_id),
                "raw": {},
            }
        ]
    )

    updated = await backfill_nubank_categories(banking_session)

    assert updated == 0
    category = (
        await banking_session.execute(
            select(TransactionModel.category).where(TransactionModel.id == row_id)
        )
    ).scalar_one()
    assert category == "Already Set"
