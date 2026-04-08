from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.models.auth import OutboxMessageModel
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class PublisherProtocol(Protocol):
    async def publish(self, *, routing_key: str, payload: dict) -> None: ...


class OutboxWorker:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        publisher: PublisherProtocol,
        batch_size: int = 100,
        poll_interval_seconds: float = 1.0,
        max_retries: int = 10,
    ) -> None:
        self._session_factory = session_factory
        self._publisher = publisher
        self._batch_size = batch_size
        self._poll_interval_seconds = poll_interval_seconds
        self._max_retries = max_retries

    async def run(self, *, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            processed_count = await self._process_batch()

            if processed_count == 0:
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self._poll_interval_seconds,
                    )
                except asyncio.TimeoutError:
                    continue

    async def _process_batch(self) -> int:
        async with self._session_factory() as session:
            messages = await self._fetch_pending_messages(session)
            if not messages:
                return 0

            for message in messages:
                await self._process_message(session, message)

            await session.commit()
            return len(messages)

    async def _fetch_pending_messages(
        self,
        session: AsyncSession,
    ) -> list[OutboxMessageModel]:
        stmt = (
            select(OutboxMessageModel)
            .where(OutboxMessageModel.status == "pending")
            .order_by(OutboxMessageModel.created_at.asc())
            .limit(self._batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _process_message(
        self,
        session: AsyncSession,
        message: OutboxMessageModel,
    ) -> None:
        try:
            await self._publisher.publish(
                routing_key=message.routing_key,
                payload=message.message_body,
            )
        except Exception as exc:
            message.retry_count += 1
            message.error_log = str(exc)[:4000]

            logger.exception(
                "outbox publish failed",
                extra={
                    "routing_key": message.routing_key,
                    "message_id": str(message.id),
                    "retry_count": message.retry_count,
                },
            )

            if message.retry_count >= self._max_retries:
                message.status = "failed"
                message.processed_at = datetime.now(timezone.utc)
            else:
                message.status = "pending"
                message.processed_at = None

            return

        logger.info(
            "outbox message processed",
            extra={
                "routing_key": message.routing_key,
                "message_id": str(message.id),
            },
        )
        message.status = "published"
        message.processed_at = datetime.now(timezone.utc)
        message.error_log = None
