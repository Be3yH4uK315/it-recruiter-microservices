from __future__ import annotations

import json
from unittest.mock import AsyncMock

import aio_pika
import pytest

from app.infrastructure.messaging.publisher import EventPublisher


@pytest.mark.asyncio
async def test_publisher_connect_declares_exchange(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = AsyncMock()
    channel = AsyncMock()
    channel.declare_exchange = AsyncMock(return_value=exchange)

    connection = AsyncMock()
    connection.channel = AsyncMock(return_value=channel)

    connect_mock = AsyncMock(return_value=connection)
    monkeypatch.setattr(aio_pika, "connect_robust", connect_mock)

    publisher = EventPublisher(
        amqp_url="amqp://guest:guest@localhost:5672/",
        exchange_name="app.events",
    )

    await publisher.connect()

    connect_mock.assert_awaited_once()
    connection.channel.assert_awaited_once_with(publisher_confirms=True)
    channel.declare_exchange.assert_awaited_once_with(
        "app.events",
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )


@pytest.mark.asyncio
async def test_publisher_publish_sends_json_message() -> None:
    exchange = AsyncMock()
    publisher = EventPublisher(
        amqp_url="amqp://guest:guest@localhost:5672/",
        exchange_name="app.events",
    )
    publisher._exchange = exchange  # type: ignore[attr-defined]

    payload = {"event": "created", "id": "123"}

    await publisher.publish(
        routing_key="employer.created",
        payload=payload,
    )

    exchange.publish.assert_awaited_once()

    message_arg = exchange.publish.await_args.args[0]
    routing_key = exchange.publish.await_args.kwargs["routing_key"]

    assert routing_key == "employer.created"
    assert message_arg.content_type == "application/json"
    assert json.loads(message_arg.body.decode("utf-8")) == payload


@pytest.mark.asyncio
async def test_publisher_publish_raises_when_not_connected() -> None:
    publisher = EventPublisher(
        amqp_url="amqp://guest:guest@localhost:5672/",
        exchange_name="app.events",
    )

    with pytest.raises(RuntimeError, match="publisher is not connected"):
        await publisher.publish(
            routing_key="employer.created",
            payload={"id": "123"},
        )


@pytest.mark.asyncio
async def test_publisher_close_closes_channel_and_connection() -> None:
    channel = AsyncMock()
    channel.is_closed = False

    connection = AsyncMock()
    connection.is_closed = False

    publisher = EventPublisher(
        amqp_url="amqp://guest:guest@localhost:5672/",
        exchange_name="app.events",
    )
    publisher._channel = channel  # type: ignore[attr-defined]
    publisher._connection = connection  # type: ignore[attr-defined]

    await publisher.close()

    channel.close.assert_awaited_once()
    connection.close.assert_awaited_once()
