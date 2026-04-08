from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.models.auth import OutboxMessageModel
from app.infrastructure.db.repositories.outbox import SqlAlchemyOutboxRepository
from app.infrastructure.messaging.outbox_worker import OutboxWorker


class StubPublisher:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    async def publish(self, *, routing_key: str, payload: dict) -> None:
        self.messages.append((routing_key, payload))


class FailingPublisher:
    async def publish(self, *, routing_key: str, payload: dict) -> None:
        raise RuntimeError("publish failed")


@pytest.mark.asyncio
async def test_outbox_worker_processes_pending_messages(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SqlAlchemyOutboxRepository(session)
        await repo.publish(routing_key="auth.user.created", payload={"user_id": "1"})
        await session.commit()

    publisher = StubPublisher()
    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=10,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed_count = await worker._process_batch()

    assert processed_count == 1
    assert publisher.messages == [("auth.user.created", {"user_id": "1"})]

    async with session_factory() as session:
        items = (await session.execute(OutboxMessageModel.__table__.select())).all()

        assert len(items) == 1

        result = await session.get(OutboxMessageModel, items[0][0])
        assert result is not None
        assert result.status == "published"
        assert result.processed_at is not None
        assert result.error_log is None


@pytest.mark.asyncio
async def test_outbox_worker_marks_failed_after_max_retries(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SqlAlchemyOutboxRepository(session)
        await repo.publish(routing_key="auth.user.created", payload={"user_id": "1"})
        await session.commit()

    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=FailingPublisher(),
        batch_size=10,
        poll_interval_seconds=0.01,
        max_retries=1,
    )

    processed_count = await worker._process_batch()

    assert processed_count == 1

    async with session_factory() as session:
        result = await session.execute(OutboxMessageModel.__table__.select())
        rows = result.all()
        assert len(rows) == 1

        message_id = rows[0][0]
        message = await session.get(OutboxMessageModel, message_id)
        assert message is not None
        assert message.status == "failed"
        assert message.retry_count == 1
        assert message.error_log == "publish failed"


@pytest.mark.asyncio
async def test_outbox_worker_run_stops_when_event_is_set(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=StubPublisher(),
        batch_size=10,
        poll_interval_seconds=0.01,
        max_retries=1,
    )

    stop_event = asyncio.Event()
    stop_event.set()

    await worker.run(stop_event=stop_event)
