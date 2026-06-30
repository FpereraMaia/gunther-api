"""Property-based tests for the Item domain entity using Hypothesis.

Hypothesis generates hundreds of edge-case inputs automatically.
These tests verify structural invariants that must hold for ALL valid inputs,
not just the handful of examples a developer would write by hand.
"""
from __future__ import annotations

import uuid

from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.item.entity import Item

# Exclude surrogate characters (Cs category) — they are invalid UTF-8 sequences
# and would cause encoding errors in JSON serialisation.
_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
    max_size=255,
)
_description = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    max_size=5000,
)


@given(name=_text, description=_description)
def test_item_stores_arbitrary_name_and_description(name: str, description: str) -> None:
    item = Item(name=name, description=description)
    assert item.name == name
    assert item.description == description


@given(name=_text)
def test_every_item_gets_a_unique_uuid(name: str) -> None:
    a = Item(name=name)
    b = Item(name=name)
    assert a.id != b.id
    assert isinstance(a.id, uuid.UUID)


@given(original=_text, updated=_text, description=_description)
def test_update_name_preserves_description(
    original: str, updated: str, description: str
) -> None:
    item = Item(name=original, description=description)
    item.update(name=updated)
    assert item.name == updated
    assert item.description == description  # untouched


@given(name=_text, new_description=_description)
def test_update_description_preserves_name(name: str, new_description: str) -> None:
    item = Item(name=name, description="original desc")
    item.update(description=new_description)
    assert item.description == new_description
    assert item.name == name  # untouched


@given(name=_text, description=_description)
@settings(max_examples=200)
def test_update_with_none_values_is_a_no_op(name: str, description: str) -> None:
    item = Item(name=name, description=description)
    item.update(name=None, description=None)
    assert item.name == name
    assert item.description == description
