"""factory-boy factories — produce domain entities with realistic fake data.

Usage in tests:

    from tests.factories import ItemFactory

    item = ItemFactory()                        # one item with generated fields
    items = ItemFactory.build_batch(10)         # ten items, nothing persisted
    item = ItemFactory(name="Widget", description="")  # override specific fields

Factories use the domain entity classes directly, so they work in unit tests
(no database or HTTP stack required).
"""
from __future__ import annotations

import factory
import factory.fuzzy

from app.domain.item.entity import Item


class ItemFactory(factory.Factory):
    class Meta:
        model = Item

    name = factory.Sequence(lambda n: f"Test Item {n}")
    description = factory.Faker("sentence", nb_words=6)
