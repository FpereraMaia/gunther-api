from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pyzipper

from app.infrastructure.banking.gmail.client import GmailClient
from app.infrastructure.banking.importers.base import ParsedTransaction, RawSource

logger = logging.getLogger(__name__)

_SENDER = "no-reply@c6bank.com.br"
_SEARCH = f"from:{_SENDER} has:attachment filename:zip"


@dataclass
class C6Importer:
    gmail: GmailClient
    bank: str = "c6"
    account_type: str = "credit_card"
    zip_password: str = ""

    def fetch_new_sources(self, seen_refs: set[str]) -> list[RawSource]:
        sources: list[RawSource] = []
        for msg_id, filename, data in self.gmail.fetch_attachments(_SEARCH, ext=".zip"):
            if msg_id in seen_refs:
                logger.info("c6.skip_known", extra={"msg_id": msg_id})
                continue
            billing_date = _billing_date_from_filename(filename)
            sources.append(RawSource(source_ref=msg_id, billing_date=billing_date, data=data))
        return sources

    def parse(self, source: RawSource) -> tuple[str, list[ParsedTransaction]]:
        password = self.zip_password.encode()
        with pyzipper.AESZipFile(io.BytesIO(source.data)) as zf:
            names = zf.namelist()
            csv_name = next((n for n in names if n.lower().endswith(".csv")), names[0])
            raw_bytes = zf.read(csv_name, pwd=password)

        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        transactions: list[ParsedTransaction] = []
        card_last4 = ""

        for row in reader:
            tx = _parse_row(row)
            if tx is None:
                continue
            if not card_last4:
                card_last4 = row.get("Final do Cartão", "").strip()
            transactions.append(tx)

        return card_last4, transactions


def _billing_date_from_filename(filename: str) -> date:
    # Fatura_2026-06-10.csv  or  Fatura_2026-06-10.zip
    try:
        stem = filename.rsplit(".", 1)[0]  # strip extension
        date_part = stem.split("_")[-1]  # "2026-06-10"
        return datetime.strptime(date_part, "%Y-%m-%d").date()
    except Exception:
        return date.today()


def _parse_row(row: dict[str, str]) -> ParsedTransaction | None:
    raw_amount = row.get("Valor (em R$)", "").strip().replace(",", ".")
    try:
        amount_brl = Decimal(raw_amount)
    except InvalidOperation:
        return None

    raw_date = row.get("Data de Compra", "").strip()
    try:
        tx_date = datetime.strptime(raw_date, "%d/%m/%Y").date()
    except ValueError:
        return None

    description = row.get("Descrição", "").strip().strip('"')
    category = row.get("Categoria", "").strip() or None
    if category == "-":
        category = None

    installment_current: int | None = None
    installment_total: int | None = None
    parcela = row.get("Parcela", "").strip()
    if "/" in parcela:
        parts = parcela.split("/")
        try:
            installment_current = int(parts[0])
            installment_total = int(parts[1])
        except ValueError:
            pass

    amount_usd_raw = row.get("Valor (em US$)", "0").strip().replace(",", ".")
    exchange_raw = row.get("Cotação (em R$)", "0").strip().replace(",", ".")
    try:
        amount_usd = Decimal(amount_usd_raw) if amount_usd_raw else None
        exchange_rate = Decimal(exchange_raw) if exchange_raw else None
    except InvalidOperation:
        amount_usd = None
        exchange_rate = None

    return ParsedTransaction(
        date=tx_date,
        description=description,
        category=category,
        amount_brl=amount_brl,
        amount_usd=amount_usd if amount_usd else None,
        exchange_rate=exchange_rate if exchange_rate else None,
        installment_current=installment_current,
        installment_total=installment_total,
        raw=dict(row),
    )
