"""Unit tests for the `sync_bank` use case.

`BankingRepository` is patched at the module level used by `sync_bank` so the
use case's orchestration logic (which sources get fetched/parsed, how errors
are aggregated, how rows are built for insert) can be exercised without a
real database or Gmail connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.banking.use_cases import sync_bank as sync_bank_module
from app.application.banking.use_cases.sync_bank import sync_bank
from app.domain.banking.entities import BankAccount, ImportJob
from app.infrastructure.banking.importers.base import ParsedTransaction, RawSource, make_row_hash


@dataclass
class FakeImporter:
    """In-memory stand-in for a `BankImporter` (C6/Nubank)."""

    bank: str = "fake"
    account_type: str = "credit_card"
    sources: list[RawSource] = field(default_factory=list)
    parsed: dict[str, tuple[str, list[ParsedTransaction]]] = field(default_factory=dict)
    raise_on: set[str] = field(default_factory=set)
    fetch_calls: list[set[str]] = field(default_factory=list)

    def fetch_new_sources(self, seen_refs: set[str]) -> list[RawSource]:
        self.fetch_calls.append(seen_refs)
        return [s for s in self.sources if s.source_ref not in seen_refs]

    def parse(self, source: RawSource) -> tuple[str, list[ParsedTransaction]]:
        if source.source_ref in self.raise_on:
            raise ValueError(f"boom: {source.source_ref}")
        return self.parsed[source.source_ref]


def _account(bank: str = "fake") -> BankAccount:
    return BankAccount(
        id=MagicMock(),
        bank=bank,
        account_type="credit_card",
        card_last4="1234",
        owner_name="Felipe",
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


def _job(source_ref: str) -> ImportJob:
    return ImportJob(
        id=MagicMock(),
        bank_account_id=MagicMock(),
        source_type="gmail",
        source_ref=source_ref,
        billing_date=date(2026, 6, 1),
        row_count=0,
        status="success",
        imported_at=MagicMock(),
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


def _tx(description: str = "Test Tx", amount: str = "10.00") -> ParsedTransaction:
    return ParsedTransaction(
        date=date(2026, 6, 1), description=description, category=None, amount_brl=Decimal(amount)
    )


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.list_import_jobs.return_value = []
    repo.get_or_create_account.return_value = _account()
    repo.create_import_job.side_effect = lambda **kwargs: _job(kwargs["source_ref"])
    repo.bulk_insert_transactions.side_effect = lambda rows: len(rows)
    return repo


@pytest.fixture(autouse=True)
def patch_repository(monkeypatch: pytest.MonkeyPatch, mock_repo: AsyncMock) -> AsyncMock:
    monkeypatch.setattr(sync_bank_module, "BankingRepository", MagicMock(return_value=mock_repo))
    return mock_repo


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


async def test_no_new_sources_returns_empty_result(
    session: AsyncMock, mock_repo: AsyncMock
) -> None:
    importer = FakeImporter(bank="nubank")

    result = await sync_bank(importer, session)

    assert result.bank == "nubank"
    assert result.sources_found == 0
    assert result.sources_imported == 0
    assert result.transactions_inserted == 0
    assert result.errors == []
    mock_repo.create_import_job.assert_not_called()
    session.commit.assert_awaited_once()


async def test_seen_refs_built_from_existing_import_jobs(
    session: AsyncMock, mock_repo: AsyncMock
) -> None:
    mock_repo.list_import_jobs.return_value = [_job("msg-old-1"), _job("msg-old-2")]
    importer = FakeImporter(bank="nubank")

    await sync_bank(importer, session)

    assert importer.fetch_calls == [{"msg-old-1", "msg-old-2"}]
    mock_repo.list_import_jobs.assert_awaited_once_with(bank="nubank")


async def test_happy_path_imports_source_and_inserts_transactions(
    session: AsyncMock, mock_repo: AsyncMock
) -> None:
    source = RawSource(source_ref="msg-1", billing_date=date(2026, 6, 1), data=b"raw")
    importer = FakeImporter(
        bank="nubank",
        sources=[source],
        parsed={"msg-1": ("", [_tx("Uber"), _tx("Netflix", "39.90")])},
    )

    result = await sync_bank(importer, session, owner_name="Felipe")

    assert result.sources_found == 1
    assert result.sources_imported == 1
    assert result.transactions_inserted == 2
    assert result.errors == []
    mock_repo.get_or_create_account.assert_awaited_once_with(
        "nubank", "", "Felipe", account_type="credit_card"
    )
    session.commit.assert_awaited_once()


async def test_bulk_insert_rows_contain_expected_fields_and_row_hash(
    session: AsyncMock, mock_repo: AsyncMock
) -> None:
    billing_date = date(2026, 6, 1)
    source = RawSource(source_ref="msg-1", billing_date=billing_date, data=b"raw")
    tx = _tx("Uber", "23.40")
    importer = FakeImporter(bank="nubank", sources=[source], parsed={"msg-1": ("", [tx])})

    await sync_bank(importer, session)

    rows: list[dict[str, Any]] = mock_repo.bulk_insert_transactions.await_args.args[0]
    assert len(rows) == 1
    row = rows[0]
    assert row["description"] == "Uber"
    assert row["amount_brl"] == 23.40
    assert row["row_hash"] == make_row_hash("nubank", billing_date, tx)


async def test_partial_dedup_insert_reflected_in_result(
    session: AsyncMock, mock_repo: AsyncMock
) -> None:
    source = RawSource(source_ref="msg-1", billing_date=date(2026, 6, 1), data=b"raw")
    importer = FakeImporter(
        bank="nubank", sources=[source], parsed={"msg-1": ("", [_tx(), _tx("other")])}
    )
    mock_repo.bulk_insert_transactions.side_effect = None
    mock_repo.bulk_insert_transactions.return_value = 1  # one row was a duplicate

    result = await sync_bank(importer, session)

    assert result.transactions_inserted == 1
    assert result.sources_imported == 1


async def test_parse_error_is_captured_and_does_not_abort_remaining_sources(
    session: AsyncMock, mock_repo: AsyncMock
) -> None:
    bad = RawSource(source_ref="msg-bad", billing_date=date(2026, 6, 1), data=b"raw")
    good = RawSource(source_ref="msg-good", billing_date=date(2026, 6, 1), data=b"raw")
    importer = FakeImporter(
        bank="c6",
        sources=[bad, good],
        parsed={"msg-good": ("1234", [_tx()])},
        raise_on={"msg-bad"},
    )

    result = await sync_bank(importer, session)

    assert result.sources_found == 2
    assert result.sources_imported == 1
    assert result.transactions_inserted == 1
    assert len(result.errors) == 1
    assert "msg-bad" in result.errors[0]
    assert "boom" in result.errors[0]
    session.commit.assert_awaited_once()


async def test_empty_transaction_list_does_not_call_bulk_insert_with_falsy_short_circuit(
    session: AsyncMock, mock_repo: AsyncMock
) -> None:
    source = RawSource(source_ref="msg-1", billing_date=date(2026, 6, 1), data=b"raw")
    importer = FakeImporter(bank="nubank", sources=[source], parsed={"msg-1": ("", [])})

    result = await sync_bank(importer, session)

    mock_repo.bulk_insert_transactions.assert_awaited_once_with([])
    assert result.sources_imported == 1
    assert result.transactions_inserted == 0
