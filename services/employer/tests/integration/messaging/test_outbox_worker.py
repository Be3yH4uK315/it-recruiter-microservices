from __future__ import annotations

from sqlalchemy import select

from app.infrastructure.db.models.employer import OutboxMessage
from app.infrastructure.messaging.outbox_worker import OutboxWorker


class StubPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish(self, *, routing_key: str, payload: dict) -> None:
        self.published.append((routing_key, payload))


async def test_outbox_worker_processes_pending_messages(session_factory) -> None:
    async with session_factory() as session:
        session.add(
            OutboxMessage(
                routing_key="employer.created",
                message_body={"employer_id": "123"},
                status="pending",
                retry_count=0,
            )
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

    processed = await worker._process_batch()
    assert processed == 1
    assert publisher.published == [("employer.created", {"employer_id": "123"})]

    async with session_factory() as session:
        result = await session.execute(select(OutboxMessage))
        message = result.scalar_one()

    assert message.status == "published"
    assert message.retry_count == 0
    assert message.error_log is None
    assert message.processed_at is not None
