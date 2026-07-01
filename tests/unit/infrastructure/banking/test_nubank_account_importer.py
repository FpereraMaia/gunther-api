"""Unit tests for `NubankAccountImporter` CSV parsing (Nubank checking-account extract)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from app.infrastructure.banking.importers.base import RawSource
from app.infrastructure.banking.importers.nubank_account import (
    NubankAccountImporter,
    _account_number_from_filename,
    _billing_date_from_filename,
)

_CSV_HEADER = "Data,Valor,Identificador,Descrição\n"
_FILENAME = "NU_70254102_01JAN2026_31JAN2026.csv"


def _importer() -> NubankAccountImporter:
    return NubankAccountImporter(gmail=MagicMock())


def _source(body: str, filename: str = _FILENAME) -> RawSource:
    return RawSource(
        source_ref="msg-1",
        billing_date=date(2026, 1, 31),
        data=(_CSV_HEADER + body).encode("utf-8"),
        filename=filename,
    )


# ── parse ───────────────────────────────────────────────────────────────────


def test_parse_incoming_pix_is_negative_after_sign_flip() -> None:
    row = (
        "04/01/2026,3240.37,695ac578-64f4-4c60-be05-0d7917aed8ce,"
        "Transferência recebida pelo Pix - FELIPE\n"
    )
    account_number, transactions = _importer().parse(_source(row))
    assert account_number == "70254102"
    assert len(transactions) == 1
    tx = transactions[0]
    assert tx.date == date(2026, 1, 4)
    assert tx.amount_brl == Decimal("-3240.37")  # money in -> negative (not spend)
    assert tx.external_id == "695ac578-64f4-4c60-be05-0d7917aed8ce"


def test_parse_outgoing_pix_is_positive_after_sign_flip() -> None:
    row = (
        "09/01/2026,-19.00,69616427-754f-4993-8ed9-06d678e6deef,"
        "Compra no débito - BY CUCA DELIVERY\n"
    )
    _, transactions = _importer().parse(_source(row))
    assert transactions[0].amount_brl == Decimal("19.00")  # money out -> positive spend


def test_parse_categorizes_known_merchant() -> None:
    row = (
        "25/01/2026,-61.55,6976a841-885d-47c0-aa08-818cce5a2b51,"
        "Compra no débito via NuPay - Zé Delivery\n"
    )
    _, transactions = _importer().parse(_source(row))
    assert transactions[0].category == "Restaurante / Lanchonete / Bar"


def test_parse_categorizes_fatura_payment() -> None:
    row = "04/01/2026,-3240.37,695ac58f-078c-4aa8-8a87-cadd504e80af,Pagamento de fatura\n"
    _, transactions = _importer().parse(_source(row))
    assert transactions[0].category == "Pagamento de Fatura"


def test_parse_skips_rows_with_invalid_date() -> None:
    row = "not-a-date,10.00,some-id,Some description\n"
    _, transactions = _importer().parse(_source(row))
    assert transactions == []


def test_parse_skips_rows_with_invalid_amount() -> None:
    row = "04/01/2026,not-a-number,some-id,Some description\n"
    _, transactions = _importer().parse(_source(row))
    assert transactions == []


def test_parse_falls_back_to_latin1_on_decode_error() -> None:
    body = "04/01/2026,-10.00,some-id,Padaria São José\n"
    raw = (_CSV_HEADER + body).encode("latin-1")
    _, transactions = _importer().parse(
        RawSource(source_ref="msg-1", billing_date=date(2026, 1, 31), data=raw, filename=_FILENAME)
    )
    assert transactions[0].description == "Padaria São José"


def test_parse_keeps_raw_row() -> None:
    row = "04/01/2026,-10.00,some-id,Some description\n"
    _, transactions = _importer().parse(_source(row))
    assert transactions[0].raw == {
        "Data": "04/01/2026",
        "Valor": "-10.00",
        "Identificador": "some-id",
        "Descrição": "Some description",
    }


def test_parse_multiple_rows() -> None:
    body = (
        "04/01/2026,-10.00,id-1,Some description\n"
        "05/01/2026,2005.45,id-2,Transferência Recebida\n"
    )
    _, transactions = _importer().parse(_source(body))
    assert len(transactions) == 2


# ── _billing_date_from_filename ──────────────────────────────────────────────


def test_billing_date_from_filename_uses_period_end_date() -> None:
    assert _billing_date_from_filename(_FILENAME) == date(2026, 1, 31)


def test_billing_date_from_filename_falls_back_to_today_on_bad_format() -> None:
    assert _billing_date_from_filename("unexpected.csv") == date.today()


def test_billing_date_from_filename_falls_back_to_today_on_unknown_month() -> None:
    assert _billing_date_from_filename("NU_123_01XXX2026_31XXX2026.csv") == date.today()


# ── _account_number_from_filename ────────────────────────────────────────────


def test_account_number_from_filename() -> None:
    assert _account_number_from_filename(_FILENAME) == "70254102"


def test_account_number_from_filename_returns_empty_on_bad_format() -> None:
    assert _account_number_from_filename("unexpected.csv") == ""


# ── fetch_new_sources ─────────────────────────────────────────────────────────


def test_fetch_new_sources_filters_out_credit_card_invoices() -> None:
    gmail = MagicMock()
    gmail.fetch_attachments.return_value = [
        ("msg-1", "Nubank_2026-01-07.csv", b"credit card invoice"),
        ("msg-2", _FILENAME, b"account extract"),
    ]
    importer = NubankAccountImporter(gmail=gmail)

    sources = importer.fetch_new_sources(seen_refs=set())

    assert [s.source_ref for s in sources] == ["msg-2"]
    assert sources[0].billing_date == date(2026, 1, 31)
    assert sources[0].filename == _FILENAME


def test_fetch_new_sources_skips_seen_refs() -> None:
    gmail = MagicMock()
    gmail.fetch_attachments.return_value = [
        ("msg-1", "NU_70254102_01DEZ2025_31DEZ2025.csv", b"data1"),
        ("msg-2", _FILENAME, b"data2"),
    ]
    importer = NubankAccountImporter(gmail=gmail)

    sources = importer.fetch_new_sources(seen_refs={"msg-1"})

    assert [s.source_ref for s in sources] == ["msg-2"]
