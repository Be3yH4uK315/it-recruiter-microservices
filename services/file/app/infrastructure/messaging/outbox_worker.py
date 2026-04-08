from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.models.file import OutboxMessage
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
            message_ids = await self._fetch_pending_message_ids(session)
            if not message_ids:
                return 0

        processed_count = 0

        for message_id in message_ids:
            was_processed = await self._process_single_message(message_id)
            if was_processed:
                processed_count += 1

        return processed_count

    async def _fetch_pending_message_ids(
        self,
        session: AsyncSession,
    ) -> list[UUID]:
        stmt = (
            select(OutboxMessage.id)
            .where(OutboxMessage.status == "pending")
            .order_by(OutboxMessage.created_at.asc())
            .limit(self._batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _process_single_message(self, message_id: UUID) -> bool:
        async with self._session_factory() as session:
            stmt = (
                select(OutboxMessage)
                .where(OutboxMessage.id == message_id)
                .with_for_update(skip_locked=True)
            )
            result = await session.execute(stmt)
            message = result.scalar_one_or_none()

            if message is None:
                return False

            if message.status != "pending":
                return False

            try:
                await self._publisher.publish(
                    routing_key=message.routing_key,
                    payload=message.message_body,
                )
            except Exception as exc:
                message.retry_count += 1
                message.error_log = str(exc)[:4000]

                if message.retry_count >= self._max_retries:
                    message.status = "failed"
                    message.processed_at = datetime.now(timezone.utc)
                else:
                    message.status = "pending"
                    message.processed_at = None

                await session.commit()

                logger.exception(
                    "outbox publish failed",
                    extra={
                        "routing_key": message.routing_key,
                        "message_id": str(message.id),
                        "retry_count": message.retry_count,
                        "status": message.status,
                    },
                )
                return True

            message.status = "published"
            message.processed_at = datetime.now(timezone.utc)
            message.error_log = None

            await session.commit()

            logger.info(
                "outbox message published",
                extra={
                    "routing_key": message.routing_key,
                    "message_id": str(message.id),
                },
            )
            return True
