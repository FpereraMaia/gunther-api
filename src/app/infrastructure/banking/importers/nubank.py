from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.infrastructure.banking.gmail.client import GmailClient
from app.infrastructure.banking.importers.base import ParsedTransaction, RawSource
from app.infrastructure.banking.importers.categorizer import infer_category
from app.infrastructure.banking.importers.nubank_account import (
    FILENAME_RE as _ACCOUNT_EXTRACT_FILENAME_RE,
)

logger = logging.getLogger(__name__)

_SENDER = "todomundo@nubank.com.br"
_SEARCH = f"from:{_SENDER} has:attachment filename:csv"
_PARCELA_RE = re.compile(r"^(.+?)\s*-\s*Parcela\s+(\d+)/(\d+)\s*$", re.IGNORECASE)


@dataclass
class NubankImporter:
    gmail: GmailClient
    bank: str = "nubank"
    account_type: str = "credit_card"

    def fetch_new_sources(self, seen_refs: set[str]) -> list[RawSource]:
        sources: list[RawSource] = []
        for msg_id, filename, data in self.gmail.fetch_attachments(_SEARCH, ext=".csv"):
            if _ACCOUNT_EXTRACT_FILENAME_RE.match(filename):
                continue  # account-extract attachment — handled by NubankAccountImporter
            if msg_id in seen_refs:
                logger.info("nubank.skip_known", extra={"msg_id": msg_id})
                continue
            billing_date = _billing_date_from_filename(filename)
            sources.append(RawSource(source_ref=msg_id, billing_date=billing_date, data=data))
        return sources

    def parse(self, source: RawSource) -> tuple[str, list[ParsedTransaction]]:
        try:
            text = source.data.decode("utf-8")
        except UnicodeDecodeError:
            text = source.data.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))
        transactions: list[ParsedTransaction] = []

        for row in reader:
            tx = _parse_row(row)
            if tx is not None:
                transactions.append(tx)

        return "", transactions  # Nubank doesn't expose card_last4 in CSV


def _billing_date_from_filename(filename: str) -> date:
    # Nubank_2026-07-07.csv
    try:
        stem = filename.rsplit(".", 1)[0]
        date_part = stem.split("_", 1)[-1]
        return datetime.strptime(date_part, "%Y-%m-%d").date()
    except Exception:
        return date.today()


def _parse_brl(value: str) -> Decimal | None:
    v = value.strip().strip('"')
    negative = v.startswith("-") or v.startswith("- ")
    v = v.lstrip("- ").strip()
    v = v.replace(".", "").replace(",", ".")
    try:
        result = Decimal(v)
        return -result if negative else result
    except InvalidOperation:
        return None


def _parse_row(row: dict[str, str]) -> ParsedTransaction | None:
    raw_date = row.get("date", "").strip()
    try:
        tx_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return None

    amount_brl = _parse_brl(row.get("amount", ""))
    if amount_brl is None:
        return None

    title = row.get("title", "").strip()
    description = title
    installment_current: int | None = None
    installment_total: int | None = None

    m = _PARCELA_RE.match(title)
    if m:
        description = m.group(1).strip()
        try:
            installment_current = int(m.group(2))
            installment_total = int(m.group(3))
        except ValueError:
            pass

    return ParsedTransaction(
        date=tx_date,
        description=description,
        category=infer_category(description),
        amount_brl=amount_brl,
        installment_current=installment_current,
        installment_total=installment_total,
        raw=dict(row),
    )
