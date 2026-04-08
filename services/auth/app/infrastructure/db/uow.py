from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.uow import UnitOfWork
from app.infrastructure.db.repositories.auth import (
    SqlAlchemyAuthUserRepository,
    SqlAlchemyRefreshSessionRepository,
)
from app.infrastructure.db.repositories.outbox import SqlAlchemyOutboxRepository
from app.infrastructure.messaging.event_mapper import DefaultEventMapper


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = SqlAlchemyAuthUserRepository(session)
        self.refresh_sessions = SqlAlchemyRefreshSessionRepository(session)
        self.outbox = SqlAlchemyOutboxRepository(session)
        self.event_mapper = DefaultEventMapper()

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            await self.rollback()

    async def flush(self) -> None:
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
