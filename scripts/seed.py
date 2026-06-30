"""Seed 10 sample Items for local development.

Usage:
    make seed
    # which runs: PYTHONPATH=src uv run python -m scripts.seed
"""
from __future__ import annotations

import asyncio
import uuid

from app.infrastructure.database.item.model import ItemModel
from app.infrastructure.database.session import unit_of_work


async def seed() -> None:
    async with unit_of_work() as session:
        for i in range(1, 11):
            session.add(
                ItemModel(
                    id=uuid.uuid4(),
                    name=f"Sample Item {i}",
                    description=f"Auto-generated seed item number {i}.",
                )
            )
    print("Seeded 10 items.")


if __name__ == "__main__":
    asyncio.run(seed())
