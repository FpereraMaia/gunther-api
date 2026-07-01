from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.banking.use_cases.backfill_categories import backfill_nubank_categories
from app.application.banking.use_cases.sync_bank import sync_bank
from app.infrastructure.database.banking.repository import BankingRepository
from app.infrastructure.database.session import get_db_session
from app.infrastructure.security.auth import UserContext, get_user
from app.presentation.api.v1.banking.schemas import (
    BankAccountResponse,
    DescriptionSummaryEntry,
    ImportJobResponse,
    PaginatedTransactionsResponse,
    SummaryEntry,
    SyncResponse,
    TransactionResponse,
)
from app.shared.config import settings

if TYPE_CHECKING:
    from app.infrastructure.banking.gmail.client import GmailClient
    from app.infrastructure.banking.importers.base import BankImporter

router = APIRouter(
    prefix="/api/v1/banking",
    tags=["banking"],
    responses={401: {"description": "Not authenticated"}},
)

_Auth = Annotated[UserContext, Depends(get_user)]
_DB = Annotated[AsyncSession, Depends(get_db_session)]


def _gmail_client() -> GmailClient:
    from app.infrastructure.banking.gmail.client import GmailClient

    return GmailClient(
        credentials_path=settings.gmail_credentials_path,
        token_path=settings.gmail_token_path,
    )


def _c6_importer() -> BankImporter:
    from app.infrastructure.banking.importers.c6 import C6Importer

    return C6Importer(gmail=_gmail_client(), zip_password=settings.c6_zip_password)


def _nubank_importer() -> BankImporter:
    from app.infrastructure.banking.importers.nubank import NubankImporter

    return NubankImporter(gmail=_gmail_client())


_IMPORTERS = {"c6": _c6_importer, "nubank": _nubank_importer}


@router.post("/sync", response_model=SyncResponse)
async def sync(
    user: _Auth,
    session: _DB,
    bank: str = Query(description="Bank to sync: c6, nubank, or 'all'", default="all"),
) -> SyncResponse:
    banks = list(_IMPORTERS.keys()) if bank == "all" else [bank]
    combined = SyncResponse(
        bank=bank, sources_found=0, sources_imported=0, transactions_inserted=0, errors=[]
    )

    for b in banks:
        if b not in _IMPORTERS:
            combined.errors.append(f"Unknown bank: {b}")
            continue
        importer = _IMPORTERS[b]()
        result = await sync_bank(importer, session, owner_name=user.username)
        combined.sources_found += result.sources_found
        combined.sources_imported += result.sources_imported
        combined.transactions_inserted += result.transactions_inserted
        combined.errors.extend(result.errors)

    return combined


@router.post("/backfill-categories", response_model=dict)
async def backfill_categories(user: _Auth, session: _DB) -> dict[str, int]:
    updated = await backfill_nubank_categories(session)
    return {"updated": updated}


@router.get("/accounts", response_model=list[BankAccountResponse])
async def list_accounts(user: _Auth, session: _DB) -> list[BankAccountResponse]:
    repo = BankingRepository(session)
    accounts = await repo.list_accounts()
    return [
        BankAccountResponse(
            id=a.id,
            bank=a.bank,
            account_type=a.account_type,
            card_last4=a.card_last4,
            owner_name=a.owner_name,
        )
        for a in accounts
    ]


@router.get("/statements", response_model=list[ImportJobResponse])
async def list_statements(
    user: _Auth,
    session: _DB,
    bank: str | None = Query(default=None),
) -> list[ImportJobResponse]:
    repo = BankingRepository(session)
    jobs = await repo.list_import_jobs_with_bank(bank=bank)

    return [
        ImportJobResponse(
            id=job.id,
            bank=job_bank,
            source_ref=job.source_ref,
            billing_date=job.billing_date,
            row_count=job.row_count,
            status=job.status,
            imported_at=job.imported_at,
        )
        for job, job_bank in jobs
    ]


@router.get("/transactions", response_model=PaginatedTransactionsResponse)
async def list_transactions(
    user: _Auth,
    session: _DB,
    bank: str | None = Query(default=None),
    card_last4: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    category: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> PaginatedTransactionsResponse:
    repo = BankingRepository(session)
    txs, total = await repo.list_transactions(
        bank=bank,
        from_date=from_date,
        to_date=to_date,
        category=category,
        card_last4=card_last4,
        offset=offset,
        limit=limit,
    )

    accounts = await repo.list_accounts_by_ids({tx.bank_account_id for tx in txs})

    return PaginatedTransactionsResponse(
        items=[
            TransactionResponse(
                id=tx.id,
                bank=accounts[tx.bank_account_id].bank if tx.bank_account_id in accounts else "",
                card_last4=accounts[tx.bank_account_id].card_last4
                if tx.bank_account_id in accounts
                else "",
                date=tx.date,
                description=tx.description,
                category=tx.category,
                amount_brl=tx.amount_brl,
                installment_current=tx.installment_current,
                installment_total=tx.installment_total,
            )
            for tx in txs
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/summary/by-description", response_model=list[DescriptionSummaryEntry])
async def summary_by_description(
    user: _Auth,
    session: _DB,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    bank: str | None = Query(default=None),
    category: str | None = Query(default=None),
    min_total: float | None = Query(
        default=None, description="Filter descriptions with total above this value"
    ),
) -> list[DescriptionSummaryEntry]:
    repo = BankingRepository(session)
    rows = await repo.get_summary_by_description(
        from_date=from_date,
        to_date=to_date,
        bank=bank,
        category=category,
        min_total=min_total,
    )
    return [DescriptionSummaryEntry(**r) for r in rows]


@router.get("/summary", response_model=list[SummaryEntry])
async def get_summary(
    user: _Auth,
    session: _DB,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    bank: str | None = Query(default=None),
) -> list[SummaryEntry]:
    repo = BankingRepository(session)
    rows = await repo.get_summary(from_date=from_date, to_date=to_date, bank=bank)
    return [SummaryEntry(**r) for r in rows]
