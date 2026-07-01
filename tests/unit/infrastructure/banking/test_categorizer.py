"""Unit tests for the rule-based category inference used by Nubank imports."""

from __future__ import annotations

import pytest

from app.infrastructure.banking.importers.categorizer import infer_category


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("IFOOD *RESTAURANTE XYZ", "Restaurante / Lanchonete / Bar"),
        ("PADARIA DO ZE", "Restaurante / Lanchonete / Bar"),
        ("SUPERMERCADO ANGELONI", "Supermercados / Mercearia / Padarias / Lojas de Conveniência"),
        ("DROGASIL FILIAL 12", "Assistência médica e odontológica"),
        ("POSTO IPIRANGA", "Relacionados a Automotivo"),
        ("99POP *VIAGEM", "Transporte"),
        ("AMAZON.COM.BR", "Departamento / Desconto"),
        ("NETFLIX.COM", "Entretenimento"),
        ("VIVO TELEFONIA", "Telecomunicações"),
        ("UDEMY *CURSO PYTHON", "Educacional"),
        ("SMARTFIT ACADEMIA", "Esporte / Saúde"),
        ("LOTERICA CENTRAL", "Lazer / Jogos"),
        ("TRANSFERENCIA PIX", "Transferência / Pix"),
        ("RENNER LOJA 10", "Vestuário / Roupas"),
        ("PETZ FILIAL", "Pet"),
    ],
)
def test_infer_category_matches_expected_rule(description: str, expected: str) -> None:
    assert infer_category(description) == expected


def test_infer_category_is_case_insensitive() -> None:
    assert infer_category("netflix.com") == infer_category("NETFLIX.COM")


def test_infer_category_returns_none_when_no_rule_matches() -> None:
    assert infer_category("COMPLETELY UNRECOGNIZABLE MERCHANT 12345") is None


def test_uber_eats_matches_food_delivery_before_transport_rule() -> None:
    # "uber.*eat" is listed before the generic "uber" transport rule, so
    # "UBER EATS" must resolve to food delivery, not transport. This guards
    # against the two rules being reordered (first match wins).
    assert infer_category("UBER EATS BRASIL") == "Restaurante / Lanchonete / Bar"


def test_plain_uber_matches_transport_rule() -> None:
    assert infer_category("UBER *TRIP 123") == "Transporte"


def test_99_embedded_in_account_number_does_not_match_transport_rule() -> None:
    # Regression: bare "99" used to match any digit run containing it, so Pix
    # descriptions with account numbers like "...Conta: 93879934-4" were
    # miscategorized as "Transporte" just because "99" appears inside the number.
    description = (
        "Transferência enviada pelo Pix - Victor Gomes - •••.655.849-•• "
        "- NU PAGAMENTOS - IP (0260) Agência: 1 Conta: 93879934-4"
    )
    assert infer_category(description) == "Transferência / Pix"
