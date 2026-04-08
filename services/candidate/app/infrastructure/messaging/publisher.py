from __future__ import annotations

import json

import aio_pika


class EventPublisher:
    def __init__(self, *, amqp_url: str, exchange_name: str) -> None:
        self._amqp_url = amqp_url
        self._exchange_name = exchange_name
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._amqp_url)
        self._channel = await self._connection.channel(publisher_confirms=True)
        self._exchange = await self._channel.declare_exchange(
            self._exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

    async def publish(self, *, routing_key: str, payload: dict) -> None:
        if self._exchange is None:
            raise RuntimeError("publisher is not connected")

        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            content_encoding="utf-8",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=str(payload.get("event_id")) if payload.get("event_id") else None,
            timestamp=None,
            type=str(payload.get("event_name")) if payload.get("event_name") else None,
        )

        await self._exchange.publish(message, routing_key=routing_key)

    async def close(self) -> None:
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()

        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()
