"""Integration tests for the banking HTTP endpoints.

Data is seeded through `BankingRepository` on a *committed* session
(`banking_session`, see `tests/integration/conftest.py`) because `test_client`
talks to the app over its own DB connection — an uncommitted seed would be
invisible to it.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.banking.repository import BankingRepository
from app.infrastructure.security.auth import UserContext, get_user
from app.main import app


@pytest.fixture
def authed() -> Iterator[None]:
    app.dependency_overrides[get_user] = lambda: UserContext(
        uid="u1", username="felipe", email="felipe@example.com"
    )
    yield
    app.dependency_overrides.pop(get_user, None)


@pytest.fixture
async def seeded(banking_session: AsyncSession) -> dict[str, object]:
    repo = BankingRepository(banking_session)
    nubank_account = await repo.get_or_create_account("nubank", "1234", "Felipe")
    c6_account = await repo.get_or_create_account("c6", "5678", "Felipe")

    nubank_job = await repo.create_import_job(
        bank_account_id=nubank_account.id,
        source_type="gmail",
        source_ref="seed-nubank-1",
        billing_date=date(2026, 6, 1),
        row_count=2,
    )

    rows = [
        {
            "id": uuid.uuid4(),
            "import_job_id": nubank_job.id,
            "bank_account_id": nubank_account.id,
            "date": date(2026, 6, 5),
            "description": "Uber Trip",
            "category": "Transporte",
            "amount_brl": 23.40,
            "amount_usd": None,
            "exchange_rate": None,
            "installment_current": None,
            "installment_total": None,
            "row_hash": "router-seed-1",
            "raw": {},
        },
        {
            "id": uuid.uuid4(),
            "import_job_id": nubank_job.id,
            "bank_account_id": nubank_account.id,
            "date": date(2026, 6, 6),
            "description": "Uber Trip",
            "category": "Transporte",
            "amount_brl": 18.00,
            "amount_usd": None,
            "exchange_rate": None,
            "installment_current": None,
            "installment_total": None,
            "row_hash": "router-seed-2",
            "raw": {},
        },
    ]
    await repo.bulk_insert_transactions(rows)
    await banking_session.commit()

    return {"nubank_account_id": nubank_account.id, "c6_account_id": c6_account.id}


# ── auth ────────────────────────────────────────────────────────────────────


def test_list_accounts_requires_auth(test_client: TestClient) -> None:
    response = test_client.get("/api/v1/banking/accounts")
    assert response.status_code == 401


# ── accounts ──────────────────────────────────────────────────────────────────


def test_list_accounts_returns_seeded_accounts(
    test_client: TestClient, authed: None, seeded: dict[str, object]
) -> None:
    response = test_client.get("/api/v1/banking/accounts")
    assert response.status_code == 200
    banks = {a["bank"] for a in response.json()}
    assert {"nubank", "c6"} <= banks


# ── statements ────────────────────────────────────────────────────────────────


def test_list_statements_filters_by_bank(
    test_client: TestClient, authed: None, seeded: dict[str, object]
) -> None:
    response = test_client.get("/api/v1/banking/statements", params={"bank": "nubank"})
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["source_ref"] == "seed-nubank-1"
    assert jobs[0]["bank"] == "nubank"


# ── transactions ──────────────────────────────────────────────────────────────


def test_list_transactions_includes_bank_and_card_last4(
    test_client: TestClient, authed: None, seeded: dict[str, object]
) -> None:
    response = test_client.get("/api/v1/banking/transactions", params={"bank": "nubank"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert all(item["bank"] == "nubank" for item in body["items"])
    assert all(item["card_last4"] == "1234" for item in body["items"])


def test_list_transactions_respects_pagination_params(
    test_client: TestClient, authed: None, seeded: dict[str, object]
) -> None:
    response = test_client.get(
        "/api/v1/banking/transactions", params={"bank": "nubank", "offset": 0, "limit": 1}
    )
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 1
    assert body["limit"] == 1
    assert body["offset"] == 0


# ── summary ───────────────────────────────────────────────────────────────────


def test_summary_groups_by_bank_and_category(
    test_client: TestClient, authed: None, seeded: dict[str, object]
) -> None:
    response = test_client.get("/api/v1/banking/summary", params={"bank": "nubank"})
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["bank"] == "nubank"
    assert entries[0]["category"] == "Transporte"
    assert entries[0]["total"] == pytest.approx(41.40)
    assert entries[0]["count"] == 2


def test_summary_by_description_groups_by_merchant(
    test_client: TestClient, authed: None, seeded: dict[str, object]
) -> None:
    response = test_client.get("/api/v1/banking/summary/by-description", params={"bank": "nubank"})
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["description"] == "Uber Trip"
    assert entries[0]["total"] == pytest.approx(41.40)
    assert entries[0]["count"] == 2


def test_backfill_categories_endpoint_returns_updated_count(
    test_client: TestClient, authed: None
) -> None:
    response = test_client.post("/api/v1/banking/backfill-categories")
    assert response.status_code == 200
    assert "updated" in response.json()


# ── cash-flow ─────────────────────────────────────────────────────────────────


def test_cash_flow_groups_by_month(
    test_client: TestClient, authed: None, seeded: dict[str, object]
) -> None:
    response = test_client.get("/api/v1/banking/cash-flow", params={"bank": "nubank"})
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    assert entries[0]["month"] == "2026-06-01"
    assert entries[0]["expense"] == pytest.approx(41.40)
    assert entries[0]["income"] == 0.0
    assert entries[0]["net"] == pytest.approx(-41.40)


# ── summary/spend-vs-transfers ───────────────────────────────────────────────


@pytest.fixture
async def seeded_with_transfer(banking_session: AsyncSession) -> dict[str, object]:
    repo = BankingRepository(banking_session)
    account = await repo.get_or_create_account("nubank", "70254102", "Felipe", "checking")
    job = await repo.create_import_job(
        bank_account_id=account.id,
        source_type="gmail",
        source_ref="seed-transfer-1",
        billing_date=date(2026, 6, 1),
        row_count=2,
    )
    rows = [
        {
            "id": uuid.uuid4(),
            "import_job_id": job.id,
            "bank_account_id": account.id,
            "date": date(2026, 6, 5),
            "description": "Restaurante",
            "category": "Restaurante / Lanchonete / Bar",
            "amount_brl": 40.00,
            "amount_usd": None,
            "exchange_rate": None,
            "installment_current": None,
            "installment_total": None,
            "row_hash": "transfer-seed-1",
            "raw": {},
        },
        {
            "id": uuid.uuid4(),
            "import_job_id": job.id,
            "bank_account_id": account.id,
            "date": date(2026, 6, 6),
            "description": "Pix to friend",
            "category": "Transferência / Pix",
            "amount_brl": 100.00,
            "amount_usd": None,
            "exchange_rate": None,
            "installment_current": None,
            "installment_total": None,
            "row_hash": "transfer-seed-2",
            "raw": {},
        },
    ]
    await repo.bulk_insert_transactions(rows)
    await banking_session.commit()
    return {"account_id": account.id}


def test_summary_spend_vs_transfers_separates_categories(
    test_client: TestClient, authed: None, seeded_with_transfer: dict[str, object]
) -> None:
    response = test_client.get(
        "/api/v1/banking/summary/spend-vs-transfers", params={"account_type": "checking"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["spend_total"] == pytest.approx(40.00)
    assert body["spend_count"] == 1
    assert body["transfer_total"] == pytest.approx(100.00)
    assert body["transfer_count"] == 1
    assert body["by_category"] == [
        {"category": "Restaurante / Lanchonete / Bar", "total": 40.00, "count": 1}
    ]


# ── account_type filtering ───────────────────────────────────────────────────


def test_list_transactions_filters_by_account_type(
    test_client: TestClient, authed: None, seeded_with_transfer: dict[str, object]
) -> None:
    response = test_client.get("/api/v1/banking/transactions", params={"account_type": "checking"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2


# ── transaction detail ───────────────────────────────────────────────────────


def test_get_transaction_detail_returns_full_audit_trail(
    test_client: TestClient, authed: None, seeded: dict[str, object]
) -> None:
    list_response = test_client.get("/api/v1/banking/transactions", params={"bank": "nubank"})
    transaction_id = list_response.json()["items"][0]["id"]

    response = test_client.get(f"/api/v1/banking/transactions/{transaction_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == transaction_id
    assert body["bank"] == "nubank"
    assert body["import_source_ref"] == "seed-nubank-1"
    assert body["row_hash"] in {"router-seed-1", "router-seed-2"}


def test_get_transaction_detail_404_for_unknown_id(test_client: TestClient, authed: None) -> None:
    response = test_client.get(f"/api/v1/banking/transactions/{uuid.uuid4()}")
    assert response.status_code == 404
