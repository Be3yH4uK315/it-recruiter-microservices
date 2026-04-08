from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.infrastructure.messaging.outbox_worker import OutboxWorker


class FailingPublisher:
    def __init__(self, error: Exception | None = None) -> None:
        self._error = error or RuntimeError("publish failed")
        self.calls = 0

    async def publish(self, *, routing_key: str, payload: dict) -> None:
        self.calls += 1
        raise self._error


class DummySessionContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def execute(self, stmt):
        return SimpleNamespace(
            scalar_one_or_none=lambda: None,
        )

    async def commit(self) -> None:
        return None


class DummySessionFactory:
    def __init__(self, session: DummySessionContext | None = None) -> None:
        self._session = session or DummySessionContext()

    def __call__(self):
        return self._session


@pytest.mark.asyncio
async def test_outbox_worker_returns_zero_on_empty_batch() -> None:
    worker = OutboxWorker(
        session_factory=DummySessionFactory(),  # type: ignore[arg-type]
        publisher=FailingPublisher(),
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )
    worker._fetch_pending_message_ids = AsyncMock(return_value=[])  # type: ignore[method-assign]

    processed = await worker._process_batch()

    assert processed == 0


@pytest.mark.asyncio
async def test_outbox_worker_marks_failed_attempt_and_keeps_pending_before_limit() -> None:
    message = SimpleNamespace(
        id=uuid4(),
        routing_key="employer.created",
        message_body={"employer_id": "123"},
        status="pending",
        retry_count=0,
        error_log=None,
        processed_at=None,
    )
    session = DummySessionContext()
    session.execute = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(scalar_one_or_none=lambda: message)
    )
    session.commit = AsyncMock()  # type: ignore[method-assign]

    worker = OutboxWorker(
        session_factory=DummySessionFactory(session),  # type: ignore[arg-type]
        publisher=FailingPublisher(),
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed = await worker._process_single_message(message.id)

    assert processed is True
    assert message.status == "pending"
    assert message.retry_count == 1
    assert message.error_log == "publish failed"
    assert message.processed_at is None


@pytest.mark.asyncio
async def test_outbox_worker_marks_failed_after_max_retries() -> None:
    message = SimpleNamespace(
        id=uuid4(),
        routing_key="employer.created",
        message_body={"employer_id": "123"},
        status="pending",
        retry_count=2,
        error_log=None,
        processed_at=None,
    )
    session = DummySessionContext()
    session.execute = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(scalar_one_or_none=lambda: message)
    )
    session.commit = AsyncMock()  # type: ignore[method-assign]

    worker = OutboxWorker(
        session_factory=DummySessionFactory(session),  # type: ignore[arg-type]
        publisher=FailingPublisher(),
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )

    processed = await worker._process_single_message(message.id)

    assert processed is True
    assert message.status == "failed"
    assert message.retry_count == 3
    assert message.error_log == "publish failed"
    assert message.processed_at is not None


@pytest.mark.asyncio
async def test_outbox_worker_run_waits_when_no_messages() -> None:
    worker = OutboxWorker(
        session_factory=DummySessionFactory(),  # type: ignore[arg-type]
        publisher=FailingPublisher(),
        batch_size=100,
        poll_interval_seconds=0.01,
        max_retries=3,
    )
    worker._process_batch = AsyncMock(return_value=0)  # type: ignore[method-assign]

    stop_event = asyncio.Event()

    async def stop_soon() -> None:
        await asyncio.sleep(0.03)
        stop_event.set()

    task = asyncio.create_task(worker.run(stop_event=stop_event))
    stopper = asyncio.create_task(stop_soon())

    await asyncio.gather(task, stopper)

    assert stop_event.is_set()
