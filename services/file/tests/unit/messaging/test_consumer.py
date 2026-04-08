from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.messaging.consumer import CleanupRequestedConsumer


class _FakeMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.acked = False
        self.nacked = False
        self.requeue = None

    async def ack(self) -> None:
        self.acked = True

    async def nack(self, *, requeue: bool) -> None:
        self.nacked = True
        self.requeue = requeue


class _FakeQueue:
    def __init__(self) -> None:
        self.bound = False
        self.cancelled_tag = None
        self.consume_callback = None

    async def bind(self, _exchange, *, routing_key: str) -> None:
        _ = routing_key
        self.bound = True

    async def consume(self, callback):
        self.consume_callback = callback
        return "consume-tag-1"

    async def cancel(self, consume_tag: str) -> None:
        self.cancelled_tag = consume_tag


class _FakeChannel:
    def __init__(self, queue: _FakeQueue) -> None:
        self._queue = queue
        self.is_closed = False
        self.prefetch_count = None

    async def set_qos(self, *, prefetch_count: int) -> None:
        self.prefetch_count = prefetch_count

    async def declare_exchange(self, *args, **kwargs):
        _ = (args, kwargs)
        return object()

    async def declare_queue(self, *args, **kwargs):
        _ = (args, kwargs)
        return self._queue

    async def close(self) -> None:
        self.is_closed = True


class _FakeConnection:
    def __init__(self, channel: _FakeChannel) -> None:
        self._channel = channel
        self.is_closed = False

    async def channel(self):
        return self._channel

    async def close(self) -> None:
        self.is_closed = True


@pytest.mark.asyncio
async def test_on_message_invalid_payload_acknowledged() -> None:
    consumer = CleanupRequestedConsumer(
        amqp_url="amqp://test",
        exchange_name="file.events",
        queue_name="file.cleanup.requested.queue",
        routing_key="file.cleanup.requested",
        cleanup_handler_factory=lambda: None,
    )
    message = _FakeMessage(b'{"invalid": true}')

    await consumer._on_message(message)

    assert message.acked is True
    assert message.nacked is False


@pytest.mark.asyncio
async def test_on_message_handler_error_nacks_with_requeue() -> None:
    class FailingHandler:
        async def __call__(self, _command):
            raise RuntimeError("boom")

    consumer = CleanupRequestedConsumer(
        amqp_url="amqp://test",
        exchange_name="file.events",
        queue_name="file.cleanup.requested.queue",
        routing_key="file.cleanup.requested",
        cleanup_handler_factory=lambda: FailingHandler(),
    )
    message = _FakeMessage(
        b'{"file_id":"11111111-1111-1111-1111-111111111111","reason":"cleanup","requested_by_service":"candidate-service"}'
    )

    await consumer._on_message(message)

    assert message.nacked is True
    assert message.requeue is True


@pytest.mark.asyncio
async def test_on_message_success_acknowledged() -> None:
    called = {"value": False}

    class Handler:
        async def __call__(self, _command):
            called["value"] = True

    consumer = CleanupRequestedConsumer(
        amqp_url="amqp://test",
        exchange_name="file.events",
        queue_name="file.cleanup.requested.queue",
        routing_key="file.cleanup.requested",
        cleanup_handler_factory=lambda: Handler(),
    )
    message = _FakeMessage(
        b'{"file_id":"11111111-1111-1111-1111-111111111111","reason":"cleanup","requested_by_service":"candidate-service"}'
    )

    await consumer._on_message(message)

    assert called["value"] is True
    assert message.acked is True
    assert message.nacked is False


@pytest.mark.asyncio
async def test_connect_run_and_close(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = _FakeQueue()
    channel = _FakeChannel(queue)
    connection = _FakeConnection(channel)

    async def fake_connect_robust(_amqp_url: str):
        return connection

    monkeypatch.setattr(
        "app.infrastructure.messaging.consumer.aio_pika.connect_robust",
        fake_connect_robust,
    )

    consumer = CleanupRequestedConsumer(
        amqp_url="amqp://test",
        exchange_name="file.events",
        queue_name="file.cleanup.requested.queue",
        routing_key="file.cleanup.requested",
        cleanup_handler_factory=lambda: None,
    )

    stop_event = asyncio.Event()

    async def stop_soon():
        await asyncio.sleep(0.01)
        stop_event.set()

    await asyncio.gather(consumer.run(stop_event=stop_event), stop_soon())

    assert channel.prefetch_count == 32
    assert queue.bound is True
    assert queue.consume_callback is not None
    assert queue.cancelled_tag == "consume-tag-1"
    assert channel.is_closed is True
    assert connection.is_closed is True
