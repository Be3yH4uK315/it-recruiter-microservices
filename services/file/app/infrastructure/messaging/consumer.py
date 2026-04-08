from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from uuid import UUID

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from app.application.files.commands.cleanup_file import CleanupFileCommand, CleanupFileHandler
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class CleanupRequestedConsumer:
    def __init__(
        self,
        *,
        amqp_url: str,
        exchange_name: str,
        queue_name: str,
        routing_key: str,
        cleanup_handler_factory: Callable[[], CleanupFileHandler],
    ) -> None:
        self._amqp_url = amqp_url
        self._exchange_name = exchange_name
        self._queue_name = queue_name
        self._routing_key = routing_key
        self._cleanup_handler_factory = cleanup_handler_factory

        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None
        self._queue: aio_pika.abc.AbstractQueue | None = None
        self._consume_tag: str | None = None

    async def run(self, *, stop_event: asyncio.Event) -> None:
        await self._connect()

        try:
            await stop_event.wait()
        finally:
            await self.close()

    async def _connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._amqp_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=32)

        exchange = await self._channel.declare_exchange(
            self._exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        self._queue = await self._channel.declare_queue(
            self._queue_name,
            durable=True,
        )
        await self._queue.bind(exchange, routing_key=self._routing_key)
        self._consume_tag = await self._queue.consume(self._on_message)

        logger.info(
            "cleanup consumer started",
            extra={
                "exchange": self._exchange_name,
                "queue": self._queue_name,
                "routing_key": self._routing_key,
            },
        )

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        payload: dict | None = None

        try:
            payload = json.loads(message.body.decode("utf-8"))
            file_id = UUID(str(payload["file_id"]))
            reason = str(payload["reason"]).strip()
            requested_by_service = str(payload["requested_by_service"]).strip()

            if not reason:
                raise ValueError("reason must not be empty")
            if not requested_by_service:
                raise ValueError("requested_by_service must not be empty")
        except Exception:
            logger.exception("cleanup consumer received invalid message payload")
            await message.ack()
            return

        try:
            handler = self._cleanup_handler_factory()
            await handler(
                CleanupFileCommand(
                    file_id=file_id,
                    reason=reason,
                    requested_by_service=requested_by_service,
                )
            )
        except Exception:
            logger.exception(
                "cleanup consumer failed to process message",
                extra={"payload": payload},
            )
            await message.nack(requeue=True)
            return

        await message.ack()

    async def close(self) -> None:
        if self._queue is not None and self._consume_tag is not None:
            try:
                await self._queue.cancel(self._consume_tag)
            except Exception:
                logger.exception("failed to cancel cleanup consumer")

        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()

        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()

        logger.info("cleanup consumer stopped")
