from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class BankAccountResponse(BaseModel):
    id: uuid.UUID
    bank: str
    account_type: str
    card_last4: str
    owner_name: str


class ImportJobResponse(BaseModel):
    id: uuid.UUID
    bank: str
    source_ref: str
    billing_date: date
    row_count: int
    status: str
    imported_at: datetime


class TransactionResponse(BaseModel):
    id: uuid.UUID
    bank: str
    card_last4: str
    date: date
    description: str
    category: str | None
    amount_brl: Decimal
    installment_current: int | None
    installment_total: int | None


class PaginatedTransactionsResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    offset: int
    limit: int


class SummaryEntry(BaseModel):
    bank: str
    category: str | None
    total: float
    count: int


class DescriptionSummaryEntry(BaseModel):
    bank: str
    description: str
    category: str | None
    total: float
    count: int


class SyncResponse(BaseModel):
    bank: str
    sources_found: int
    sources_imported: int
    transactions_inserted: int
    errors: list[str]


class CashFlowEntry(BaseModel):
    month: date
    income: float
    expense: float
    net: float
    count: int


class CategoryTotal(BaseModel):
    category: str | None
    total: float
    count: int


class SpendVsTransfersResponse(BaseModel):
    spend_total: float
    spend_count: int
    transfer_total: float
    transfer_count: int
    by_category: list[CategoryTotal]


class TransactionDetailResponse(BaseModel):
    id: uuid.UUID
    bank: str
    account_type: str
    card_last4: str
    import_job_id: uuid.UUID
    import_source_ref: str
    import_billing_date: date
    imported_at: datetime
    date: date
    description: str
    category: str | None
    amount_brl: Decimal
    amount_usd: Decimal | None
    exchange_rate: Decimal | None
    installment_current: int | None
    installment_total: int | None
    row_hash: str
    raw: dict[str, Any]
