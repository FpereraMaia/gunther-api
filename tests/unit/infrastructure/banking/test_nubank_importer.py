"""Unit tests for `NubankImporter` CSV parsing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from app.infrastructure.banking.importers.base import RawSource
from app.infrastructure.banking.importers.nubank import (
    NubankImporter,
    _billing_date_from_filename,
    _parse_brl,
)

_CSV_HEADER = "date,title,amount\n"


def _importer() -> NubankImporter:
    return NubankImporter(gmail=MagicMock())


def _source(body: str) -> RawSource:
    return RawSource(
        source_ref="msg-1", billing_date=date(2026, 6, 10), data=(_CSV_HEADER + body).encode()
    )


# ── parse ───────────────────────────────────────────────────────────────────


def test_parse_simple_row() -> None:
    card_last4, transactions = _importer().parse(_source('2026-06-05,Uber *Trip,"23,40"\n'))
    assert card_last4 == ""  # Nubank CSV never exposes card_last4
    assert len(transactions) == 1
    tx = transactions[0]
    assert tx.date == date(2026, 6, 5)
    assert tx.description == "Uber *Trip"
    assert tx.amount_brl == Decimal("23.40")
    assert tx.category == "Transporte"


def test_parse_negative_amount_is_payment_or_refund() -> None:
    _, transactions = _importer().parse(_source('2026-06-05,Pagamento recebido,"-150,00"\n'))
    assert transactions[0].amount_brl == Decimal("-150.00")


def test_parse_installment_title_splits_description_and_counts() -> None:
    _, transactions = _importer().parse(_source("2026-06-05,Magazine Luiza - Parcela 2/10,99.90\n"))
    tx = transactions[0]
    assert tx.description == "Magazine Luiza"
    assert tx.installment_current == 2
    assert tx.installment_total == 10
    assert tx.category == "Departamento / Desconto"


def test_parse_skips_rows_with_invalid_date() -> None:
    _, transactions = _importer().parse(_source("not-a-date,Some Title,10.00\n"))
    assert transactions == []


def test_parse_skips_rows_with_invalid_amount() -> None:
    _, transactions = _importer().parse(_source("2026-06-05,Some Title,not-a-number\n"))
    assert transactions == []


def test_parse_multiple_rows() -> None:
    body = "2026-06-01,Netflix,39.90\n2026-06-02,Uber *Trip,18.00\n"
    _, transactions = _importer().parse(_source(body))
    assert len(transactions) == 2


def test_parse_falls_back_to_latin1_on_decode_error() -> None:
    raw = (_CSV_HEADER + "2026-06-05,Padaria São José,12.50\n").encode("latin-1")
    _, transactions = _importer().parse(
        RawSource(source_ref="msg-1", billing_date=date(2026, 6, 10), data=raw)
    )
    assert transactions[0].description == "Padaria São José"


def test_parse_keeps_raw_row() -> None:
    _, transactions = _importer().parse(_source("2026-06-05,Uber *Trip,23.40\n"))
    assert transactions[0].raw == {"date": "2026-06-05", "title": "Uber *Trip", "amount": "23.40"}


# ── _parse_brl ────────────────────────────────────────────────────────────────


def test_parse_brl_plain() -> None:
    assert _parse_brl("23,40") == Decimal("23.40")


def test_parse_brl_brazilian_thousands_format() -> None:
    assert _parse_brl("1.234,56") == Decimal("1234.56")


def test_parse_brl_negative() -> None:
    assert _parse_brl("-150,00") == Decimal("-150.00")


def test_parse_brl_invalid_returns_none() -> None:
    assert _parse_brl("not-a-number") is None


# ── _billing_date_from_filename ──────────────────────────────────────────────


def test_billing_date_from_filename_parses_date() -> None:
    assert _billing_date_from_filename("Nubank_2026-07-07.csv") == date(2026, 7, 7)


def test_billing_date_from_filename_falls_back_to_today_on_bad_format() -> None:
    assert _billing_date_from_filename("unexpected.csv") == date.today()


# ── fetch_new_sources ─────────────────────────────────────────────────────────


def test_fetch_new_sources_skips_seen_refs() -> None:
    gmail = MagicMock()
    gmail.fetch_attachments.return_value = [
        ("msg-1", "Nubank_2026-06-01.csv", b"data1"),
        ("msg-2", "Nubank_2026-07-01.csv", b"data2"),
    ]
    importer = NubankImporter(gmail=gmail)

    sources = importer.fetch_new_sources(seen_refs={"msg-1"})

    assert [s.source_ref for s in sources] == ["msg-2"]
    assert sources[0].billing_date == date(2026, 7, 1)
    assert sources[0].data == b"data2"


def test_fetch_new_sources_ignores_account_extract_attachments() -> None:
    # Same sender/search as NubankAccountImporter's — must not claim its files.
    gmail = MagicMock()
    gmail.fetch_attachments.return_value = [
        ("msg-1", "NU_70254102_01JAN2026_31JAN2026.csv", b"extract"),
        ("msg-2", "Nubank_2026-07-01.csv", b"invoice"),
    ]
    importer = NubankImporter(gmail=gmail)

    sources = importer.fetch_new_sources(seen_refs=set())

    assert [s.source_ref for s in sources] == ["msg-2"]
