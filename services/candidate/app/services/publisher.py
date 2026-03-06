import asyncio
import logging

import aio_pika

from app.core.config import settings

logger = logging.getLogger(__name__)


class RabbitMQProducer:
    def __init__(self):
        self.connection_string = (
            f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASS}@"
            f"{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/"
        )
        self.connection = None
        self.channel = None
        self.exchange = None
        self.dlq_exchange = None
        self._lock = asyncio.Lock()

    async def connect(self):
        """Устанавливает соединение с RabbitMQ."""
        async with self._lock:
            if self.connection and not self.connection.is_closed:
                return

            logger.info("Connecting to RabbitMQ producer...")
            try:
                self.connection = await aio_pika.connect_robust(self.connection_string)
                self.channel = await self.connection.channel()
                self.exchange = await self.channel.declare_exchange(
                    settings.CANDIDATE_EXCHANGE_NAME,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )
                self.dlq_exchange = await self.channel.declare_exchange(
                    settings.DLQ_EXCHANGE_NAME,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )

                logger.info("Successfully connected to RabbitMQ.")
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                raise

    async def publish_message(self, routing_key: str, message_body: bytes):
        if not self.connection or self.connection.is_closed:
            await self.connect()

        try:
            message = aio_pika.Message(
                body=message_body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await self.exchange.publish(message, routing_key=routing_key)
            logger.debug(f"Published to RabbitMQ: {routing_key}")
        except Exception as e:
            logger.error(f"Failed to publish to RabbitMQ: {e}")
            raise e

    async def publish_dlq(self, routing_key: str, message_body: bytes, error_info: str):
        """Отправка в DLQ при фатальном сбое после ретраев."""
        if not self.connection or self.connection.is_closed:
            await self.connect()

        try:
            headers = {"x-error-info": str(error_info)}
            message = aio_pika.Message(
                body=message_body,
                content_type="application/json",
                headers=headers,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await self.dlq_exchange.publish(message, routing_key=routing_key)
            logger.warning(f"Message moved to DLQ: {routing_key}")
        except Exception as e:
            logger.critical(f"CRITICAL: Failed to publish to DLQ! Event lost? {e}")
            raise e

    async def close(self):
        if self.connection:
            await self.connection.close()
            logger.info("RabbitMQ connection closed.")


publisher = RabbitMQProducer()
