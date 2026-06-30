"""Unit tests for `C6Importer` — AES-ZIP decryption + semicolon-CSV parsing."""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import pyzipper

from app.infrastructure.banking.importers.base import RawSource
from app.infrastructure.banking.importers.c6 import C6Importer, _billing_date_from_filename

_PASSWORD = "123456"
_HEADER = (
    "Data de Compra;Descrição;Categoria;Parcela;Valor (em R$);"
    "Valor (em US$);Cotação (em R$);Final do Cartão\n"
)


def _make_zip(csv_body: str, password: str = _PASSWORD) -> bytes:
    buf = io.BytesIO()
    with pyzipper.AESZipFile(
        buf, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as zf:
        zf.setpassword(password.encode())
        zf.writestr("fatura.csv", (_HEADER + csv_body).encode("utf-8"))
    return buf.getvalue()


def _importer(password: str = _PASSWORD) -> C6Importer:
    return C6Importer(gmail=MagicMock(), zip_password=password)


def _source(data: bytes) -> RawSource:
    return RawSource(source_ref="msg-1", billing_date=date(2026, 6, 10), data=data)


# ── parse ───────────────────────────────────────────────────────────────────


def test_parse_decrypts_and_parses_row() -> None:
    zip_bytes = _make_zip("10/06/2026;Uber Trip;Transporte;;23,40;0;0;1234\n")
    card_last4, transactions = _importer().parse(_source(zip_bytes))

    assert card_last4 == "1234"
    assert len(transactions) == 1
    tx = transactions[0]
    assert tx.date == date(2026, 6, 10)
    assert tx.description == "Uber Trip"
    assert tx.category == "Transporte"
    assert tx.amount_brl == Decimal("23.40")


def test_parse_wrong_password_raises() -> None:
    zip_bytes = _make_zip("10/06/2026;Uber Trip;Transporte;;23,40;0;0;1234\n")
    with pytest.raises(RuntimeError):
        _importer(password="000000").parse(_source(zip_bytes))


def test_parse_category_dash_becomes_none() -> None:
    zip_bytes = _make_zip("10/06/2026;Some Store;-;;23,40;0;0;1234\n")
    _, transactions = _importer().parse(_source(zip_bytes))
    assert transactions[0].category is None


def test_parse_installments() -> None:
    zip_bytes = _make_zip("10/06/2026;Magazine Luiza;Departamento;3/12;99,90;0;0;1234\n")
    _, transactions = _importer().parse(_source(zip_bytes))
    tx = transactions[0]
    assert tx.installment_current == 3
    assert tx.installment_total == 12


def test_parse_usd_amount_and_exchange_rate() -> None:
    zip_bytes = _make_zip("10/06/2026;Apple.com;Entretenimento;;55,00;10,00;5,50;1234\n")
    _, transactions = _importer().parse(_source(zip_bytes))
    tx = transactions[0]
    assert tx.amount_usd == Decimal("10.00")
    assert tx.exchange_rate == Decimal("5.50")


def test_parse_skips_rows_with_invalid_amount() -> None:
    zip_bytes = _make_zip("10/06/2026;Bad Row;Categoria;;not-a-number;0;0;1234\n")
    _, transactions = _importer().parse(_source(zip_bytes))
    assert transactions == []


def test_parse_skips_rows_with_invalid_date() -> None:
    zip_bytes = _make_zip("not-a-date;Bad Row;Categoria;;23,40;0;0;1234\n")
    _, transactions = _importer().parse(_source(zip_bytes))
    assert transactions == []


def test_parse_card_last4_taken_from_first_row() -> None:
    zip_bytes = _make_zip(
        "10/06/2026;First;Categoria;;10,00;0;0;5678\n11/06/2026;Second;Categoria;;20,00;0;0;5678\n"
    )
    card_last4, transactions = _importer().parse(_source(zip_bytes))
    assert card_last4 == "5678"
    assert len(transactions) == 2


def test_parse_falls_back_to_latin1_on_decode_error() -> None:
    csv_body = "10/06/2026;Padaria São José;Restaurante;;12,50;0;0;1234\n"
    buf = io.BytesIO()
    with pyzipper.AESZipFile(
        buf, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as zf:
        zf.setpassword(_PASSWORD.encode())
        zf.writestr("fatura.csv", (_HEADER + csv_body).encode("latin-1"))

    _, transactions = _importer().parse(_source(buf.getvalue()))
    assert transactions[0].description == "Padaria São José"


def test_parse_non_numeric_installment_is_ignored() -> None:
    zip_bytes = _make_zip("10/06/2026;Some Store;Categoria;x/y;23,40;0;0;1234\n")
    _, transactions = _importer().parse(_source(zip_bytes))
    tx = transactions[0]
    assert tx.installment_current is None
    assert tx.installment_total is None


def test_parse_invalid_usd_amount_falls_back_to_none() -> None:
    zip_bytes = _make_zip("10/06/2026;Apple.com;Entretenimento;;55,00;bad;bad;1234\n")
    _, transactions = _importer().parse(_source(zip_bytes))
    tx = transactions[0]
    assert tx.amount_usd is None
    assert tx.exchange_rate is None


def test_parse_keeps_raw_row() -> None:
    zip_bytes = _make_zip("10/06/2026;Uber Trip;Transporte;;23,40;0;0;1234\n")
    _, transactions = _importer().parse(_source(zip_bytes))
    assert transactions[0].raw["Descrição"] == "Uber Trip"


# ── _billing_date_from_filename ──────────────────────────────────────────────


def test_billing_date_from_filename_parses_date() -> None:
    assert _billing_date_from_filename("Fatura_2026-06-10.zip") == date(2026, 6, 10)


def test_billing_date_from_filename_falls_back_to_today_on_bad_format() -> None:
    assert _billing_date_from_filename("unexpected.zip") == date.today()


# ── fetch_new_sources ─────────────────────────────────────────────────────────


def test_fetch_new_sources_skips_seen_refs() -> None:
    gmail = MagicMock()
    gmail.fetch_attachments.return_value = [
        ("msg-1", "Fatura_2026-06-10.zip", b"zip1"),
        ("msg-2", "Fatura_2026-07-10.zip", b"zip2"),
    ]
    importer = C6Importer(gmail=gmail, zip_password=_PASSWORD)

    sources = importer.fetch_new_sources(seen_refs={"msg-1"})

    assert [s.source_ref for s in sources] == ["msg-2"]
    assert sources[0].billing_date == date(2026, 7, 10)
    assert sources[0].data == b"zip2"
