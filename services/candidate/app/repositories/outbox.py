import datetime as dt
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import candidate


class OutboxRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def create(self, routing_key: str, message_body: dict) -> candidate.OutboxMessage:
        """
        Создает запись в Outbox.
        """
        db_message = candidate.OutboxMessage(
            routing_key=routing_key, message_body=message_body, status="pending"
        )
        self.session.add(db_message)
        return db_message

    async def get_pending_with_lock(self, limit: int = 100) -> list[candidate.OutboxMessage]:
        """
        Получает неотправленные сообщения с блокировкой (SKIP LOCKED).
        """
        query = (
            select(candidate.OutboxMessage)
            .where(candidate.OutboxMessage.status == "pending")
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def mark_as_sent(self, message_id: UUID):
        """
        Помечает сообщение как отправленное и ставит время обработки.
        """
        now_utc = dt.datetime.now(dt.UTC)
        query = (
            update(candidate.OutboxMessage)
            .where(candidate.OutboxMessage.id == message_id)
            .values(status="sent", processed_at=now_utc)
        )
        await self.session.execute(query)
