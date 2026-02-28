import asyncio
import structlog

from app.core.logger import setup_logging
from app.services.outbox_worker import outbox_worker
from app.services.publisher import publisher

setup_logging()
logger = structlog.get_logger()

async def main():
    logger.info("Starting Background Worker Process...")
    try:
        await publisher.connect()
    except Exception as e:
        logger.critical(f"Worker failed to connect to RabbitMQ: {e}")
        return

    worker_task = asyncio.create_task(outbox_worker.run())
    
    try:
        await worker_task
    except asyncio.CancelledError:
        logger.info("Worker stop signal received")
    finally:
        await outbox_worker.stop()
        await publisher.close()
        logger.info("Worker shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
