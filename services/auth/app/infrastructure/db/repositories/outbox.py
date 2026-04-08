from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.contracts import OutboxPort
from app.infrastructure.db.models.auth import OutboxMessageModel


class SqlAlchemyOutboxRepository(OutboxPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish(self, *, routing_key: str, payload: dict) -> None:
        self._session.add(
            OutboxMessageModel(
                routing_key=routing_key,
                message_body=payload,
                status="pending",
                retry_count=0,
                error_log=None,
            )
        )

    async def get_pending_batch(self, *, limit: int) -> list[OutboxMessageModel]:
        stmt = (
            select(OutboxMessageModel)
            .where(OutboxMessageModel.status == "pending")
            .order_by(OutboxMessageModel.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def mark_published(self, message: OutboxMessageModel) -> None:
        message.status = "published"
        message.processed_at = datetime.now(timezone.utc)
        message.error_log = None

    async def mark_failed(
        self,
        message: OutboxMessageModel,
        *,
        error: str,
        max_retries: int,
    ) -> None:
        message.retry_count += 1
        message.error_log = error[:4000]
        message.status = "failed" if message.retry_count >= max_retries else "pending"
        message.processed_at = datetime.now(timezone.utc) if message.status == "failed" else None
