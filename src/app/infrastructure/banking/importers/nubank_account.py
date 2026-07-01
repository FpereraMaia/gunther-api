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

logger = logging.getLogger(__name__)

_SENDER = "todomundo@nubank.com.br"
_SEARCH = f"from:{_SENDER} has:attachment filename:csv"

# Nubank_2026-07-07.csv (credit card invoice) also matches the search above —
# only account-extract attachments look like NU_<account>_<start>_<end>.csv.
# NubankImporter (credit card) imports this same module to skip these filenames,
# so the two importers don't race for the same Gmail messages.
FILENAME_RE = re.compile(
    r"^NU_(?P<account>\d+)_\d{2}[A-Za-z]{3}\d{4}_(?P<end>\d{2}[A-Za-z]{3}\d{4})\.csv$"
)

_MONTHS_PT = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}


@dataclass
class NubankAccountImporter:
    gmail: GmailClient
    bank: str = "nubank"
    account_type: str = "checking"

    def fetch_new_sources(self, seen_refs: set[str]) -> list[RawSource]:
        sources: list[RawSource] = []
        for msg_id, filename, data in self.gmail.fetch_attachments(_SEARCH, ext=".csv"):
            if not FILENAME_RE.match(filename):
                continue  # not an account-extract attachment (e.g. a credit card invoice)
            if msg_id in seen_refs:
                logger.info("nubank_account.skip_known", extra={"msg_id": msg_id})
                continue
            billing_date = _billing_date_from_filename(filename)
            sources.append(
                RawSource(
                    source_ref=msg_id, billing_date=billing_date, data=data, filename=filename
                )
            )
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

        account_number = _account_number_from_filename(source.filename)
        return account_number, transactions


def _parse_pt_date(value: str) -> date | None:
    # e.g. "31JAN2026"
    month = _MONTHS_PT.get(value[2:5].lower())
    if month is None:
        return None
    try:
        return date(int(value[5:]), month, int(value[:2]))
    except ValueError:
        return None


def _billing_date_from_filename(filename: str) -> date:
    m = FILENAME_RE.match(filename)
    if not m:
        return date.today()
    return _parse_pt_date(m.group("end")) or date.today()


def _account_number_from_filename(filename: str) -> str:
    m = FILENAME_RE.match(filename)
    return m.group("account") if m else ""


def _parse_row(row: dict[str, str]) -> ParsedTransaction | None:
    raw_date = row.get("Data", "").strip()
    try:
        tx_date = datetime.strptime(raw_date, "%d/%m/%Y").date()
    except ValueError:
        return None

    raw_amount = row.get("Valor", "").strip()
    try:
        raw_value = Decimal(raw_amount)
    except InvalidOperation:
        return None

    # The extract reports incoming money as positive, outgoing as negative — the
    # opposite of the "positive = spend" convention used elsewhere in this schema
    # (credit card imports, get_summary's amount_brl > 0 filter). Flip it here so
    # spend aggregation works the same regardless of account type.
    amount_brl = -raw_value

    description = row.get("Descrição", "").strip()
    external_id = row.get("Identificador", "").strip() or None

    return ParsedTransaction(
        date=tx_date,
        description=description,
        category=infer_category(description),
        amount_brl=amount_brl,
        external_id=external_id,
        raw=dict(row),
    )
