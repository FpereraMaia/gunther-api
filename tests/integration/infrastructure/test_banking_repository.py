"""Integration tests for `BankingRepository` against a real Postgres testcontainer.

Uses the `db_session` fixture (auto-rolled-back per test), since every test
here does its setup and assertions through a single session/connection.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.banking.repository import BankingRepository


def _tx_row(
    bank_account_id: uuid.UUID,
    import_job_id: uuid.UUID,
    *,
    description: str = "Uber Trip",
    category: str | None = "Transporte",
    amount_brl: float = 23.40,
    tx_date: date = date(2026, 6, 1),
    row_hash: str | None = None,
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "import_job_id": import_job_id,
        "bank_account_id": bank_account_id,
        "date": tx_date,
        "description": description,
        "category": category,
        "amount_brl": amount_brl,
        "amount_usd": None,
        "exchange_rate": None,
        "installment_current": None,
        "installment_total": None,
        "row_hash": row_hash or uuid.uuid4().hex,
        "raw": {},
    }


# ── BankAccount ───────────────────────────────────────────────────────────────


async def test_get_or_create_account_creates_new_account(db_session: AsyncSession) -> None:
    repo = BankingRepository(db_session)
    account = await repo.get_or_create_account("nubank", "1234", "Felipe")
    assert account.bank == "nubank"
    assert account.card_last4 == "1234"
    assert account.owner_name == "Felipe"


async def test_get_or_create_account_is_idempotent_on_bank_and_card(
    db_session: AsyncSession,
) -> None:
    repo = BankingRepository(db_session)
    first = await repo.get_or_create_account("nubank", "1234", "Felipe")
    second = await repo.get_or_create_account("nubank", "1234", "Someone Else")
    assert first.id == second.id
    assert second.owner_name == "Felipe"  # not overwritten on the second call


async def test_list_accounts_orders_by_bank(db_session: AsyncSession) -> None:
    repo = BankingRepository(db_session)
    await repo.get_or_create_account("nubank", "1234", "Felipe")
    await repo.get_or_create_account("c6", "5678", "Felipe")

    accounts = await repo.list_accounts()

    banks = [a.bank for a in accounts]
    assert banks == sorted(banks)
    assert {"nubank", "c6"} <= set(banks)


# ── ImportJob ─────────────────────────────────────────────────────────────────


async def test_create_and_list_import_jobs_filtered_by_bank(db_session: AsyncSession) -> None:
    repo = BankingRepository(db_session)
    nubank_account = await repo.get_or_create_account("nubank", "1234", "Felipe")
    c6_account = await repo.get_or_create_account("c6", "5678", "Felipe")

    await repo.create_import_job(
        bank_account_id=nubank_account.id,
        source_type="gmail",
        source_ref="msg-nubank-1",
        billing_date=date(2026, 6, 1),
        row_count=5,
    )
    await repo.create_import_job(
        bank_account_id=c6_account.id,
        source_type="gmail",
        source_ref="msg-c6-1",
        billing_date=date(2026, 6, 1),
        row_count=3,
    )

    nubank_jobs = await repo.list_import_jobs(bank="nubank")
    all_jobs = await repo.list_import_jobs()

    assert [j.source_ref for j in nubank_jobs] == ["msg-nubank-1"]
    assert {j.source_ref for j in all_jobs} == {"msg-nubank-1", "msg-c6-1"}


# ── Transaction / dedup ────────────────────────────────────────────────────────


async def test_bulk_insert_transactions_empty_list_returns_zero(db_session: AsyncSession) -> None:
    repo = BankingRepository(db_session)
    assert await repo.bulk_insert_transactions([]) == 0


async def test_bulk_insert_transactions_dedups_via_row_hash(db_session: AsyncSession) -> None:
    repo = BankingRepository(db_session)
    account = await repo.get_or_create_account("nubank", "1234", "Felipe")
    job = await repo.create_import_job(
        bank_account_id=account.id,
        source_type="gmail",
        source_ref="msg-1",
        billing_date=date(2026, 6, 1),
        row_count=1,
    )
    row = _tx_row(account.id, job.id, row_hash="dedup-hash-1")

    first_inserted = await repo.bulk_insert_transactions([row])
    second_inserted = await repo.bulk_insert_transactions([row])

    assert first_inserted == 1
    assert second_inserted == 0  # re-syncing the same source is a no-op


async def test_bulk_insert_transactions_partial_dedup(db_session: AsyncSession) -> None:
    repo = BankingRepository(db_session)
    account = await repo.get_or_create_account("nubank", "1234", "Felipe")
    job = await repo.create_import_job(
        bank_account_id=account.id,
        source_type="gmail",
        source_ref="msg-1",
        billing_date=date(2026, 6, 1),
        row_count=1,
    )
    existing = _tx_row(account.id, job.id, row_hash="dup-hash")
    await repo.bulk_insert_transactions([existing])

    new_row = _tx_row(account.id, job.id, row_hash="new-hash")
    inserted = await repo.bulk_insert_transactions([existing, new_row])

    assert inserted == 1


# ── list_transactions ──────────────────────────────────────────────────────────


async def test_list_transactions_filters_by_bank_card_date_and_category(
    db_session: AsyncSession,
) -> None:
    repo = BankingRepository(db_session)
    nubank_account = await repo.get_or_create_account("nubank", "1234", "Felipe")
    c6_account = await repo.get_or_create_account("c6", "5678", "Felipe")
    nubank_job = await repo.create_import_job(
        bank_account_id=nubank_account.id,
        source_type="gmail",
        source_ref="msg-nubank",
        billing_date=date(2026, 6, 1),
        row_count=2,
    )
    c6_job = await repo.create_import_job(
        bank_account_id=c6_account.id,
        source_type="gmail",
        source_ref="msg-c6",
        billing_date=date(2026, 6, 1),
        row_count=1,
    )
    await repo.bulk_insert_transactions(
        [
            _tx_row(
                nubank_account.id,
                nubank_job.id,
                description="Uber Trip",
                category="Transporte",
                tx_date=date(2026, 6, 5),
                row_hash="h1",
            ),
            _tx_row(
                nubank_account.id,
                nubank_job.id,
                description="Netflix",
                category="Entretenimento",
                tx_date=date(2026, 7, 5),
                row_hash="h2",
            ),
            _tx_row(
                c6_account.id,
                c6_job.id,
                description="Padaria",
                category="Restaurante / Lanchonete / Bar",
                tx_date=date(2026, 6, 10),
                row_hash="h3",
            ),
        ]
    )

    nubank_only, total_nubank = await repo.list_transactions(bank="nubank")
    assert total_nubank == 2
    assert {tx.description for tx in nubank_only} == {"Uber Trip", "Netflix"}

    by_card, total_card = await repo.list_transactions(card_last4="5678")
    assert total_card == 1
    assert by_card[0].description == "Padaria"

    by_date, total_date = await repo.list_transactions(
        from_date=date(2026, 6, 1), to_date=date(2026, 6, 30)
    )
    assert total_date == 2
    assert {tx.description for tx in by_date} == {"Uber Trip", "Padaria"}

    by_category, total_category = await repo.list_transactions(category="Transporte")
    assert total_category == 1
    assert by_category[0].description == "Uber Trip"


async def test_list_transactions_pagination(db_session: AsyncSession) -> None:
    repo = BankingRepository(db_session)
    account = await repo.get_or_create_account("nubank", "1234", "Felipe")
    job = await repo.create_import_job(
        bank_account_id=account.id,
        source_type="gmail",
        source_ref="msg-1",
        billing_date=date(2026, 6, 1),
        row_count=3,
    )
    await repo.bulk_insert_transactions(
        [
            _tx_row(account.id, job.id, description=f"Tx {i}", row_hash=f"page-hash-{i}")
            for i in range(3)
        ]
    )

    page1, total = await repo.list_transactions(bank="nubank", offset=0, limit=2)
    page2, _ = await repo.list_transactions(bank="nubank", offset=2, limit=2)

    assert total == 3
    assert len(page1) == 2
    assert len(page2) == 1


# ── get_summary ────────────────────────────────────────────────────────────────


async def test_get_summary_excludes_non_positive_amounts(db_session: AsyncSession) -> None:
    repo = BankingRepository(db_session)
    account = await repo.get_or_create_account("nubank", "1234", "Felipe")
    job = await repo.create_import_job(
        bank_account_id=account.id,
        source_type="gmail",
        source_ref="msg-1",
        billing_date=date(2026, 6, 1),
        row_count=2,
    )
    await repo.bulk_insert_transactions(
        [
            _tx_row(
                account.id,
                job.id,
                description="Uber",
                category="Transporte",
                amount_brl=23.40,
                row_hash="sum-1",
            ),
            _tx_row(
                account.id,
                job.id,
                description="Payment received",
                category=None,
                amount_brl=-100.00,
                row_hash="sum-2",
            ),
        ]
    )

    summary = await repo.get_summary(bank="nubank")

    assert len(summary) == 1
    assert summary[0]["category"] == "Transporte"
    assert summary[0]["total"] == 23.40
    assert summary[0]["count"] == 1


async def test_get_summary_groups_by_bank_and_category(db_session: AsyncSession) -> None:
    repo = BankingRepository(db_session)
    account = await repo.get_or_create_account("nubank", "1234", "Felipe")
    job = await repo.create_import_job(
        bank_account_id=account.id,
        source_type="gmail",
        source_ref="msg-1",
        billing_date=date(2026, 6, 1),
        row_count=2,
    )
    await repo.bulk_insert_transactions(
        [
            _tx_row(
                account.id,
                job.id,
                description="Uber 1",
                category="Transporte",
                amount_brl=10.00,
                row_hash="grp-1",
            ),
            _tx_row(
                account.id,
                job.id,
                description="Uber 2",
                category="Transporte",
                amount_brl=15.00,
                row_hash="grp-2",
            ),
        ]
    )

    summary = await repo.get_summary(bank="nubank")

    assert len(summary) == 1
    assert summary[0]["total"] == 25.00
    assert summary[0]["count"] == 2
