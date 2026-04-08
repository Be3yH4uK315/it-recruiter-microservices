from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

_CAMEL_TO_SNAKE_RE_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_TO_SNAKE_RE_2 = re.compile(r"([a-z0-9])([A-Z])")


@dataclass(slots=True, frozen=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def event_name(self) -> str:
        name = self.__class__.__name__
        step_1 = _CAMEL_TO_SNAKE_RE_1.sub(r"\1_\2", name)
        step_2 = _CAMEL_TO_SNAKE_RE_2.sub(r"\1_\2", step_1)
        return step_2.lower()
