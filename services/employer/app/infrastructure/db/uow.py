from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.uow import UnitOfWork
from app.infrastructure.db.repositories.employer import (
    SqlAlchemyContactRequestRepository,
    SqlAlchemyEmployerRepository,
    SqlAlchemySearchSessionRepository,
)
from app.infrastructure.db.repositories.outbox import SqlAlchemyOutboxRepository
from app.infrastructure.messaging.event_mapper import DefaultEventMapper


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.employers = SqlAlchemyEmployerRepository(session)
        self.searches = SqlAlchemySearchSessionRepository(session)
        self.contact_requests = SqlAlchemyContactRequestRepository(session)
        self.outbox = SqlAlchemyOutboxRepository(session)
        self.event_mapper = DefaultEventMapper()

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            await self.rollback()
            return
        await self.commit()

    async def flush(self) -> None:
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
