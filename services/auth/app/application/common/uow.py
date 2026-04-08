from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.common.contracts import EventMapper, OutboxPort
from app.domain.auth.repository import AuthUserRepository, RefreshSessionRepository


class UnitOfWork(ABC):
    users: AuthUserRepository
    refresh_sessions: RefreshSessionRepository
    outbox: OutboxPort
    event_mapper: EventMapper

    @abstractmethod
    async def __aenter__(self) -> "UnitOfWork":
        raise NotImplementedError

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None:
        raise NotImplementedError

    @abstractmethod
    async def flush(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        raise NotImplementedError
