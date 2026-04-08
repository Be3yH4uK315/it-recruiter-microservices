from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.contracts import OutboxPort
from app.infrastructure.db.models import candidate as models


class SqlAlchemyOutboxRepository(OutboxPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish(self, *, routing_key: str, payload: dict) -> None:
        message = models.OutboxMessage(
            routing_key=routing_key,
            message_body=payload,
            status="pending",
            retry_count=0,
            error_log=None,
        )
        self._session.add(message)
