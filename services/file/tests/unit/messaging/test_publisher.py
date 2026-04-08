from __future__ import annotations

import json

import pytest

from app.infrastructure.messaging.publisher import EventPublisher


class _FakeExchange:
    def __init__(self) -> None:
        self.published: list[tuple[object, str]] = []

    async def publish(self, message, routing_key: str) -> None:
        self.published.append((message, routing_key))


class _FakeChannel:
    def __init__(self, exchange: _FakeExchange) -> None:
        self._exchange = exchange
        self.is_closed = False

    async def declare_exchange(self, *args, **kwargs):
        _ = (args, kwargs)
        return self._exchange

    async def close(self) -> None:
        self.is_closed = True


class _FakeConnection:
    def __init__(self, channel: _FakeChannel) -> None:
        self._channel = channel
        self.is_closed = False

    async def channel(self, **kwargs):
        _ = kwargs
        return self._channel

    async def close(self) -> None:
        self.is_closed = True


@pytest.mark.asyncio
async def test_publish_raises_when_not_connected() -> None:
    publisher = EventPublisher(amqp_url="amqp://test", exchange_name="file.events")

    with pytest.raises(RuntimeError, match="publisher is not connected"):
        await publisher.publish(routing_key="file.created", payload={"event_id": "1"})


@pytest.mark.asyncio
async def test_connect_publish_and_close(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = _FakeExchange()
    channel = _FakeChannel(exchange)
    connection = _FakeConnection(channel)

    async def fake_connect_robust(_amqp_url: str):
        return connection

    monkeypatch.setattr(
        "app.infrastructure.messaging.publisher.aio_pika.connect_robust",
        fake_connect_robust,
    )

    publisher = EventPublisher(amqp_url="amqp://test", exchange_name="file.events")
    await publisher.connect()
    await publisher.publish(
        routing_key="file.created",
        payload={"event_id": "evt-1", "event_name": "file_created", "file_id": "f1"},
    )
    await publisher.close()

    assert len(exchange.published) == 1
    message, routing_key = exchange.published[0]
    assert routing_key == "file.created"
    assert json.loads(message.body.decode("utf-8"))["file_id"] == "f1"
    assert channel.is_closed is True
    assert connection.is_closed is True
