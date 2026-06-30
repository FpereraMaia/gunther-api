"""Item domain entity — no framework imports, no DB imports."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Item:
    name: str
    description: str = ""
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def update(
        self,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
