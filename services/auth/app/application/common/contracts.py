from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.auth.entities import RefreshSession, User
from app.domain.common.events import DomainEvent


class OutboxPort(ABC):
    @abstractmethod
    async def publish(self, *, routing_key: str, payload: dict) -> None:
        raise NotImplementedError


class EventMapper(ABC):
    @abstractmethod
    def map_domain_event(
        self,
        *,
        event: DomainEvent,
        user: User | None = None,
        refresh_session: RefreshSession | None = None,
    ) -> list[tuple[str, dict]]:
        raise NotImplementedError
