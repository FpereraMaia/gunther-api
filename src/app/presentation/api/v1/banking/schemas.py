from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

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
