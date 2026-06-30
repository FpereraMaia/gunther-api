"""Unit tests for the Item domain entity — no DB, no framework."""
from __future__ import annotations

import uuid

from app.domain.item.entity import Item


def test_item_default_id_is_uuid() -> None:
    item = Item(name="Widget")
    assert isinstance(item.id, uuid.UUID)


def test_two_items_have_different_ids() -> None:
    a = Item(name="A")
    b = Item(name="B")
    assert a.id != b.id


def test_item_default_description_is_empty() -> None:
    item = Item(name="Widget")
    assert item.description == ""


def test_update_name() -> None:
    item = Item(name="Old")
    item.update(name="New")
    assert item.name == "New"


def test_update_description() -> None:
    item = Item(name="Widget", description="old desc")
    item.update(description="new desc")
    assert item.description == "new desc"


def test_update_none_values_are_ignored() -> None:
    item = Item(name="Widget", description="desc")
    item.update(name=None, description=None)
    assert item.name == "Widget"
    assert item.description == "desc"


def test_update_partial_leaves_other_field_unchanged() -> None:
    item = Item(name="Widget", description="desc")
    item.update(name="NewWidget")
    assert item.description == "desc"
