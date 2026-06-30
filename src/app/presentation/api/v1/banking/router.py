from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

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

router = APIRouter(prefix="/api/v1/banking", tags=["banking"])

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
    from app.application.banking.use_cases.sync_bank import sync_bank

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
    from app.application.banking.use_cases.backfill_categories import backfill_nubank_categories

    updated = await backfill_nubank_categories(session)
    return {"updated": updated}


@router.get("/accounts", response_model=list[BankAccountResponse])
async def list_accounts(user: _Auth, session: _DB) -> list[BankAccountResponse]:
    from app.infrastructure.database.banking.repository import BankingRepository

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
    from sqlalchemy import select

    from app.infrastructure.database.banking.models import BankAccountModel, ImportJobModel

    q = select(ImportJobModel, BankAccountModel.bank).join(BankAccountModel)
    if bank:
        q = q.where(BankAccountModel.bank == bank)
    q = q.order_by(ImportJobModel.billing_date.desc())
    rows = (await session.execute(q)).all()

    return [
        ImportJobResponse(
            id=row.ImportJobModel.id,
            bank=row.bank,
            source_ref=row.ImportJobModel.source_ref,
            billing_date=row.ImportJobModel.billing_date,
            row_count=row.ImportJobModel.row_count,
            status=row.ImportJobModel.status,
            imported_at=row.ImportJobModel.imported_at,
        )
        for row in rows
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
    from app.infrastructure.database.banking.models import BankAccountModel
    from app.infrastructure.database.banking.repository import BankingRepository

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

    # fetch bank/card info per transaction via account ids
    account_ids = {tx.bank_account_id for tx in txs}
    from sqlalchemy import select

    accounts = {
        m.id: m
        for m in (
            await session.execute(
                select(BankAccountModel).where(BankAccountModel.id.in_(account_ids))
            )
        ).scalars()
    }

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
    from sqlalchemy import func, select

    from app.infrastructure.database.banking.models import BankAccountModel, TransactionModel

    q = (
        select(
            BankAccountModel.bank,
            TransactionModel.description,
            TransactionModel.category,
            func.sum(TransactionModel.amount_brl).label("total"),
            func.count(TransactionModel.id).label("tx_count"),
        )
        .join(BankAccountModel)
        .where(TransactionModel.amount_brl > 0)
        .group_by(BankAccountModel.bank, TransactionModel.description, TransactionModel.category)
        .order_by(func.sum(TransactionModel.amount_brl).desc())
    )
    if bank:
        q = q.where(BankAccountModel.bank == bank)
    if category:
        q = q.where(TransactionModel.category == category)
    if from_date:
        q = q.where(TransactionModel.date >= from_date)
    if to_date:
        q = q.where(TransactionModel.date <= to_date)
    if min_total:
        q = q.having(func.sum(TransactionModel.amount_brl) >= min_total)

    rows = (await session.execute(q)).all()
    return [
        DescriptionSummaryEntry(
            bank=r.bank,
            description=r.description,
            category=r.category,
            total=round(float(r.total), 2),
            count=r.tx_count,
        )
        for r in rows
    ]


@router.get("/summary", response_model=list[SummaryEntry])
async def get_summary(
    user: _Auth,
    session: _DB,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    bank: str | None = Query(default=None),
) -> list[SummaryEntry]:
    from app.infrastructure.database.banking.repository import BankingRepository

    repo = BankingRepository(session)
    rows = await repo.get_summary(from_date=from_date, to_date=to_date, bank=bank)
    return [SummaryEntry(**r) for r in rows]
