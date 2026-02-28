import asyncio
import json
import logging

from app.core.db import AsyncSessionLocal
from app.repositories.outbox import OutboxRepository
from app.services.publisher import publisher

logger = logging.getLogger(__name__)

MAX_RETRIES = 5

class OutboxWorker:
    def __init__(self, interval_seconds: int = 2):
        self.interval = interval_seconds
        self.is_running = False
        self._task = None

    async def run(self):
        logger.info("Outbox worker started.")
        self.is_running = True
        while self.is_running:
            try:
                processed_count = await self.process_batch()
                sleep_time = 0.1 if processed_count > 0 else self.interval
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                logger.info("Worker loop cancelled, shutting down...")
                break
            except Exception as e:
                logger.error(f"Outbox worker global crash: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def process_batch(self) -> int:
        async with AsyncSessionLocal() as db:
            repo = OutboxRepository(db)
            messages = await repo.get_pending_with_lock(limit=50)
            
            if not messages:
                return 0

            try:
                await publisher.connect()
            except Exception:
                logger.warning("RabbitMQ unavailable, skipping batch.")
                return 0

            processed_count = 0
            
            for msg in messages:
                body_bytes = json.dumps(msg.message_body).encode()
                
                try:
                    await publisher.publish_message(
                        routing_key=msg.routing_key,
                        message_body=body_bytes
                    )
                    await repo.mark_as_sent(msg.id)
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Failed to publish message {msg.id}: {e}")
                    
                    msg.retry_count += 1
                    msg.error_log = str(e)[:500]
                    
                    if msg.retry_count >= MAX_RETRIES:
                        logger.error(f"Message {msg.id} failed max retries. Moving to DLQ.")
                        try:
                            await publisher.publish_dlq(
                                routing_key=msg.routing_key,
                                message_body=body_bytes,
                                error_info=str(e)
                            )
                            msg.status = "failed"
                        except Exception as dlq_error:
                            logger.critical(f"Failed to move to DLQ! Data danger! {dlq_error}")
            
            await db.commit()
            return processed_count

    def start(self):
        if not self._task:
            self._task = asyncio.create_task(self.run())

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Outbox worker stopped.")

outbox_worker = OutboxWorker()