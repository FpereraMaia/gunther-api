from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass
class RawSource:
    source_ref: str
    billing_date: date
    data: bytes


@dataclass
class ParsedTransaction:
    date: date
    description: str
    category: str | None
    amount_brl: Decimal
    amount_usd: Decimal | None = None
    exchange_rate: Decimal | None = None
    installment_current: int | None = None
    installment_total: int | None = None
    raw: dict = field(default_factory=dict)


def make_row_hash(bank: str, billing_date: date, tx: ParsedTransaction) -> str:
    amount_cents = int(tx.amount_brl * 100)
    key = (
        f"{bank}|{billing_date.isoformat()}|{tx.date.isoformat()}"
        f"|{tx.description.strip().upper()}"
        f"|{amount_cents}"
        f"|{tx.installment_current or 0}|{tx.installment_total or 0}"
    )
    return hashlib.sha256(key.encode()).hexdigest()


class BankImporter(Protocol):
    bank: str

    def fetch_new_sources(self, seen_refs: set[str]) -> list[RawSource]:
        """Return sources (emails/files) not yet imported."""
        ...

    def parse(self, source: RawSource) -> tuple[str, list[ParsedTransaction]]:
        """Return (card_last4, transactions). card_last4='' if unknown."""
        ...
