from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.models.file import OutboxMessage
from app.infrastructure.messaging.outbox_worker import OutboxWorker


class StubPublisher:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.published: list[tuple[str, dict]] = []

    async def publish(
        self,
        *,
        routing_key: str,
        payload: dict,
    ) -> None:
        if self.should_fail:
            raise RuntimeError("publish failed")
        self.published.append((routing_key, payload))


async def _truncate_outbox(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await session.execute(OutboxMessage.__table__.delete())
        await session.commit()


async def _add_outbox_message(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    routing_key: str = "file.created",
    payload: dict | None = None,
    status: str = "pending",
    retry_count: int = 0,
) -> None:
    async with session_factory() as session:
        session.add(
            OutboxMessage(
                id=uuid4(),
                routing_key=routing_key,
                message_body=payload or {"hello": "world"},
                status=status,
                retry_count=retry_count,
            )
        )
        await session.commit()


async def _get_all_messages(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[OutboxMessage]:
    async with session_factory() as session:
        result = await session.execute(
            select(OutboxMessage).order_by(OutboxMessage.created_at.asc())
        )
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_process_batch_processes_pending_messages(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _truncate_outbox(session_factory)
    await _add_outbox_message(
        session_factory,
        routing_key="file.created",
        payload={"file_id": "1"},
    )
    publisher = StubPublisher()

    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed_count = await worker._process_batch()

    assert processed_count == 1
    assert publisher.published == [("file.created", {"file_id": "1"})]

    messages = await _get_all_messages(session_factory)
    assert len(messages) == 1
    assert messages[0].status == "published"
    assert messages[0].processed_at is not None
    assert messages[0].error_log is None


@pytest.mark.asyncio
async def test_process_batch_does_nothing_when_no_pending_messages(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _truncate_outbox(session_factory)
    publisher = StubPublisher()

    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed_count = await worker._process_batch()

    assert processed_count == 0
    assert publisher.published == []


@pytest.mark.asyncio
async def test_process_batch_skips_non_pending_messages(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _truncate_outbox(session_factory)
    await _add_outbox_message(
        session_factory,
        routing_key="file.created",
        payload={"file_id": "1"},
        status="published",
    )
    publisher = StubPublisher()

    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed_count = await worker._process_batch()

    assert processed_count == 0
    assert publisher.published == []


@pytest.mark.asyncio
async def test_process_batch_marks_message_failed_after_max_retries(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _truncate_outbox(session_factory)
    await _add_outbox_message(
        session_factory,
        routing_key="file.created",
        payload={"file_id": "1"},
        retry_count=2,
    )
    publisher = StubPublisher(should_fail=True)

    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed_count = await worker._process_batch()

    assert processed_count == 1

    messages = await _get_all_messages(session_factory)
    assert len(messages) == 1
    assert messages[0].status == "failed"
    assert messages[0].retry_count == 3
    assert messages[0].processed_at is not None
    assert messages[0].error_log is not None
    assert "publish failed" in messages[0].error_log


@pytest.mark.asyncio
async def test_process_batch_increments_retry_count_but_keeps_pending_before_max_retries(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _truncate_outbox(session_factory)
    await _add_outbox_message(
        session_factory,
        routing_key="file.created",
        payload={"file_id": "1"},
        retry_count=0,
    )
    publisher = StubPublisher(should_fail=True)

    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed_count = await worker._process_batch()

    assert processed_count == 1

    messages = await _get_all_messages(session_factory)
    assert len(messages) == 1
    assert messages[0].status == "pending"
    assert messages[0].retry_count == 1
    assert messages[0].processed_at is None
    assert messages[0].error_log is not None


@pytest.mark.asyncio
async def test_process_batch_respects_batch_size(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _truncate_outbox(session_factory)
    await _add_outbox_message(session_factory, payload={"file_id": "1"})
    await _add_outbox_message(session_factory, payload={"file_id": "2"})
    await _add_outbox_message(session_factory, payload={"file_id": "3"})

    publisher = StubPublisher()

    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=2,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed_count = await worker._process_batch()

    assert processed_count == 2
    assert len(publisher.published) == 2

    messages = await _get_all_messages(session_factory)
    statuses = [message.status for message in messages]
    assert statuses.count("published") == 2
    assert statuses.count("pending") == 1


@pytest.mark.asyncio
async def test_published_message_has_processed_at_timestamp(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _truncate_outbox(session_factory)
    await _add_outbox_message(session_factory, payload={"file_id": "1"})
    publisher = StubPublisher()

    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    before = datetime.now(timezone.utc)
    await worker._process_batch()
    after = datetime.now(timezone.utc)

    messages = await _get_all_messages(session_factory)
    assert len(messages) == 1
    assert messages[0].processed_at is not None
    assert before <= messages[0].processed_at <= after
