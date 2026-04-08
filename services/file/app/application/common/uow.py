from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.common.contracts import EventMapper, OutboxPort
from app.domain.file.repository import FileRepository


class UnitOfWork(ABC):
    files: FileRepository
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
