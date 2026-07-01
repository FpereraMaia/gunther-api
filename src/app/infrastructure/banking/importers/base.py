from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol


@dataclass
class RawSource:
    source_ref: str
    billing_date: date
    data: bytes
    filename: str = ""


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
    external_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def make_row_hash(bank: str, billing_date: date, tx: ParsedTransaction) -> str:
    amount_cents = int(tx.amount_brl * 100)
    # Some sources (e.g. Nubank's account extract) provide a stable per-transaction
    # id, which dedups correctly even when re-imported under a different billing_date
    # (overlapping statement periods) — so it replaces billing_date in the key.
    # It is NOT sufficient on its own: Nubank reuses one id across a pair of linked
    # legs (e.g. "added funds" + the payment that consumed them), so tx_date/amount
    # stay in the key to keep those legs distinct.
    if tx.external_id:
        key = f"{bank}|external|{tx.external_id}|{tx.date.isoformat()}|{amount_cents}"
    else:
        key = (
            f"{bank}|{billing_date.isoformat()}|{tx.date.isoformat()}"
            f"|{tx.description.strip().upper()}"
            f"|{amount_cents}"
            f"|{tx.installment_current or 0}|{tx.installment_total or 0}"
        )
    return hashlib.sha256(key.encode()).hexdigest()


class BankImporter(Protocol):
    bank: str
    account_type: str

    def fetch_new_sources(self, seen_refs: set[str]) -> list[RawSource]:
        """Return sources (emails/files) not yet imported."""
        ...

    def parse(self, source: RawSource) -> tuple[str, list[ParsedTransaction]]:
        """Return (card_last4, transactions). card_last4='' if unknown."""
        ...
