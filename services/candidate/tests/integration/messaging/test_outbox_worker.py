from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from app.infrastructure.db.models import candidate as db_models
from app.infrastructure.messaging.outbox_worker import OutboxWorker


@dataclass
class StubPublisher:
    published: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    fail_times: int = 0

    async def publish(self, *, routing_key: str, payload: dict) -> None:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("publisher failure")
        self.published.append((routing_key, payload))


async def test_outbox_worker_processes_pending_messages(session_factory) -> None:
    async with session_factory() as session:
        session.add(
            db_models.OutboxMessage(
                routing_key="candidate.created",
                message_body={"candidate_id": "c1"},
                status="pending",
                retry_count=0,
            ),
        )
        session.add(
            db_models.OutboxMessage(
                routing_key="search.candidate.sync.requested",
                message_body={"candidate_id": "c1", "operation": "upsert"},
                status="pending",
                retry_count=0,
            ),
        )
        await session.commit()

    publisher = StubPublisher()
    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed_count = await worker._process_batch()

    assert processed_count == 2
    assert publisher.published == [
        ("candidate.created", {"candidate_id": "c1"}),
        ("search.candidate.sync.requested", {"candidate_id": "c1", "operation": "upsert"}),
    ]

    async with session_factory() as session:
        result = await session.execute(
            select(db_models.OutboxMessage).order_by(db_models.OutboxMessage.created_at.asc()),
        )
        messages = list(result.scalars().all())

    assert len(messages) == 2
    assert all(message.status == "processed" for message in messages)
    assert all(message.processed_at is not None for message in messages)
    assert all(message.error_log is None for message in messages)
    assert all(message.retry_count == 0 for message in messages)


async def test_outbox_worker_increments_retry_count_on_publish_error(session_factory) -> None:
    async with session_factory() as session:
        session.add(
            db_models.OutboxMessage(
                routing_key="candidate.updated",
                message_body={"candidate_id": "c2"},
                status="pending",
                retry_count=0,
            ),
        )
        await session.commit()

    publisher = StubPublisher(fail_times=1)
    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed_count = await worker._process_batch()

    assert processed_count == 1
    assert publisher.published == []

    async with session_factory() as session:
        result = await session.execute(select(db_models.OutboxMessage))
        message = result.scalars().one()

    assert message.status == "pending"
    assert message.retry_count == 1
    assert message.error_log == "publisher failure"
    assert message.processed_at is None


async def test_outbox_worker_marks_message_failed_after_retry_limit(session_factory) -> None:
    async with session_factory() as session:
        session.add(
            db_models.OutboxMessage(
                routing_key="candidate.updated",
                message_body={"candidate_id": "c3"},
                status="pending",
                retry_count=2,
            ),
        )
        await session.commit()

    publisher = StubPublisher(fail_times=1)
    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed_count = await worker._process_batch()

    assert processed_count == 1
    assert publisher.published == []

    async with session_factory() as session:
        result = await session.execute(select(db_models.OutboxMessage))
        message = result.scalars().one()

    assert message.status == "failed"
    assert message.retry_count == 3
    assert message.error_log == "publisher failure"
    assert message.processed_at is not None


async def test_outbox_worker_run_stops_when_stop_event_is_set(session_factory) -> None:
    publisher = StubPublisher()
    worker = OutboxWorker(
        session_factory=session_factory,
        publisher=publisher,
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    stop_event = asyncio.Event()
    stop_event.set()

    await worker.run(stop_event=stop_event)

    assert publisher.published == []


async def test_outbox_worker_processes_only_pending_messages(session_factory) -> None:
    async with session_factory() as session:
        session.add(
            db_models.OutboxMessage(
                routing_key="candidate.created",
                message_body={"candidate_id": "pending"},
                status="pending",
                retry_count=0,
            ),
        )
        session.add(
            db_models.OutboxMessage(
                routing_key="candidate.created",
                message_body={"candidate_id": "processed"},
                status="processed",
                retry_count=0,
            ),
        )
        session.add(
            db_models.OutboxMessage(
                routing_key="candidate.created",
                message_body={"candidate_id": "failed"},
                status="failed",
                retry_count=5,
            ),
        )
        await session.commit()

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
    assert publisher.published == [
        ("candidate.created", {"candidate_id": "pending"}),
    ]

    async with session_factory() as session:
        result = await session.execute(select(db_models.OutboxMessage))
        messages = list(result.scalars().all())

    by_candidate_id = {message.message_body["candidate_id"]: message for message in messages}

    assert by_candidate_id["pending"].status == "processed"
    assert by_candidate_id["processed"].status == "processed"
    assert by_candidate_id["failed"].status == "failed"
