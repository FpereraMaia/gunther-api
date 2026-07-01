"""Unit tests for `make_row_hash` — the dedup key used by `bulk_insert_transactions`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.infrastructure.banking.importers.base import ParsedTransaction, make_row_hash


def _tx(**overrides: object) -> ParsedTransaction:
    defaults: dict[str, object] = {
        "date": date(2026, 6, 10),
        "description": "IFOOD *RESTAURANTE",
        "category": "Restaurante / Lanchonete / Bar",
        "amount_brl": Decimal("42.50"),
    }
    defaults.update(overrides)
    return ParsedTransaction(**defaults)


def test_same_inputs_produce_same_hash() -> None:
    tx = _tx()
    billing_date = date(2026, 6, 15)
    assert make_row_hash("nubank", billing_date, tx) == make_row_hash("nubank", billing_date, tx)


def test_different_bank_changes_hash() -> None:
    tx = _tx()
    billing_date = date(2026, 6, 15)
    assert make_row_hash("nubank", billing_date, tx) != make_row_hash("c6", billing_date, tx)


def test_different_billing_date_changes_hash() -> None:
    tx = _tx()
    assert make_row_hash("nubank", date(2026, 6, 15), tx) != make_row_hash(
        "nubank", date(2026, 7, 15), tx
    )


def test_different_amount_changes_hash() -> None:
    billing_date = date(2026, 6, 15)
    tx1 = _tx(amount_brl=Decimal("42.50"))
    tx2 = _tx(amount_brl=Decimal("42.51"))
    assert make_row_hash("nubank", billing_date, tx1) != make_row_hash("nubank", billing_date, tx2)


def test_description_case_and_whitespace_are_normalized() -> None:
    billing_date = date(2026, 6, 15)
    tx1 = _tx(description="ifood *restaurante")
    tx2 = _tx(description="  IFOOD *RESTAURANTE  ")
    assert make_row_hash("nubank", billing_date, tx1) == make_row_hash("nubank", billing_date, tx2)


def test_missing_installments_default_to_zero() -> None:
    billing_date = date(2026, 6, 15)
    tx_explicit_zero = _tx(installment_current=0, installment_total=0)
    tx_none = _tx(installment_current=None, installment_total=None)
    assert make_row_hash("nubank", billing_date, tx_explicit_zero) == make_row_hash(
        "nubank", billing_date, tx_none
    )


def test_different_installments_change_hash() -> None:
    billing_date = date(2026, 6, 15)
    tx1 = _tx(installment_current=1, installment_total=3)
    tx2 = _tx(installment_current=2, installment_total=3)
    assert make_row_hash("nubank", billing_date, tx1) != make_row_hash("nubank", billing_date, tx2)


def test_hash_is_sha256_hex_digest() -> None:
    h = make_row_hash("nubank", date(2026, 6, 15), _tx())
    assert len(h) == 64
    int(h, 16)  # raises ValueError if not valid hex


# ── external_id dedup ─────────────────────────────────────────────────────────


def test_external_id_present_ignores_billing_date_differences() -> None:
    tx = _tx(external_id="abc-123")
    assert make_row_hash("nubank", date(2026, 6, 15), tx) == make_row_hash(
        "nubank", date(2026, 7, 15), tx
    )


def test_external_id_with_different_amount_changes_hash() -> None:
    # Nubank reuses one id across a pair of linked legs (e.g. "added funds" +
    # the payment it funded) — amount must stay part of the key so both survive.
    billing_date = date(2026, 6, 15)
    tx1 = _tx(external_id="abc-123", amount_brl=Decimal("121.47"))
    tx2 = _tx(external_id="abc-123", amount_brl=Decimal("-121.47"))
    assert make_row_hash("nubank", billing_date, tx1) != make_row_hash("nubank", billing_date, tx2)


def test_external_id_with_different_date_changes_hash() -> None:
    tx1 = _tx(external_id="abc-123", date=date(2026, 6, 10))
    tx2 = _tx(external_id="abc-123", date=date(2026, 6, 11))
    billing_date = date(2026, 6, 15)
    assert make_row_hash("nubank", billing_date, tx1) != make_row_hash("nubank", billing_date, tx2)


def test_different_external_id_changes_hash() -> None:
    billing_date = date(2026, 6, 15)
    tx1 = _tx(external_id="abc-123")
    tx2 = _tx(external_id="def-456")
    assert make_row_hash("nubank", billing_date, tx1) != make_row_hash("nubank", billing_date, tx2)


def test_external_id_scoped_by_bank() -> None:
    billing_date = date(2026, 6, 15)
    tx = _tx(external_id="abc-123")
    assert make_row_hash("nubank", billing_date, tx) != make_row_hash("c6", billing_date, tx)
