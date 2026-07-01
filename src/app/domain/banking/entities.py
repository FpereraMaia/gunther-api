from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any


@dataclass
class BankAccount:
    id: uuid.UUID
    bank: str
    account_type: str
    card_last4: str
    owner_name: str
    created_at: datetime
    updated_at: datetime


@dataclass
class ImportJob:
    id: uuid.UUID
    bank_account_id: uuid.UUID
    source_type: str
    source_ref: str
    billing_date: date
    row_count: int
    status: str
    imported_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass
class Transaction:
    id: uuid.UUID
    import_job_id: uuid.UUID
    bank_account_id: uuid.UUID
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
    created_at: datetime
    updated_at: datetime


@dataclass
class TransactionDetail:
    """A transaction plus the account and import job it came from."""

    transaction: Transaction
    account: BankAccount
    import_job: ImportJob
