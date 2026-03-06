import asyncio
import json

import aio_pika
import structlog

from app.core.config import settings
from app.services.indexer import indexer

logger = structlog.get_logger()


class RabbitMQConsumer:
    def __init__(self):
        self.connection_string = (
            f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASS}@"
            f"{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/"
        )
        self.connection = None
        self.channel = None

    async def connect_and_consume(self):
        """
        Запускает цикл потребления сообщений.
        """
        while True:
            try:
                self.connection = await aio_pika.connect_robust(self.connection_string)
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=1)

                exchange = await self.channel.declare_exchange(
                    settings.CANDIDATE_EXCHANGE_NAME,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )

                queue = await self.channel.declare_queue(
                    "search_service_queue",
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": settings.DLQ_EXCHANGE_NAME,
                        "x-dead-letter-routing-key": "search_dlq",
                    },
                )

                await queue.bind(exchange, routing_key="candidate.created")
                await queue.bind(exchange, routing_key="candidate.updated.#")
                await queue.bind(exchange, routing_key="candidate.deleted")

                logger.info("RabbitMQ Consumer started. Listening for candidate events...")

                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        async with message.process():
                            await self._process_message(message)

            except Exception as e:
                logger.error(f"Consumer lost connection or crashed: {e}. Retrying in 5s...")
                await asyncio.sleep(5)

    async def _process_message(self, message: aio_pika.IncomingMessage):
        """Бизнес-логика обработки события."""
        routing_key = message.routing_key
        try:
            data = json.loads(message.body.decode())
            logger.info("Processing event", routing_key=routing_key, id=data.get("id"))

            if "deleted" in routing_key:
                candidate_id = data.get("id")
                await indexer.delete_candidate(candidate_id)
            else:
                candidate_data = data.get("payload", data)
                if "skills" not in candidate_data:
                    pass

                if "id" not in candidate_data and "id" in data:
                    candidate_data["id"] = data["id"]

                await indexer.process_candidate_update(candidate_data)

        except Exception as e:
            logger.error("Error processing message", error=str(e), routing_key=routing_key)
            raise e


consumer = RabbitMQConsumer()
