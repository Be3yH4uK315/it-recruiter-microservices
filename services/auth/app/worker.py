from __future__ import annotations

import asyncio
import signal

from app.config import get_settings
from app.infrastructure.db.session import SessionFactory, engine
from app.infrastructure.messaging.outbox_worker import OutboxWorker
from app.infrastructure.messaging.publisher import EventPublisher
from app.infrastructure.observability.logger import configure_logging, get_logger


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)

    publisher = EventPublisher(
        amqp_url=settings.rabbitmq_url,
        exchange_name=settings.rabbitmq_exchange,
    )
    worker = OutboxWorker(
        session_factory=SessionFactory,
        publisher=publisher,
        batch_size=settings.outbox_batch_size,
        poll_interval_seconds=settings.outbox_poll_interval_seconds,
        max_retries=settings.outbox_max_retries,
    )

    stop_event = asyncio.Event()

    def _stop() -> None:
        logger.info("stop signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            logger.warning(
                "signal handlers are not supported in this environment",
                extra={"signal": getattr(sig, "name", str(sig))},
            )

    try:
        logger.info(
            "worker startup",
            extra={
                "exchange": settings.rabbitmq_exchange,
                "batch_size": settings.outbox_batch_size,
                "poll_interval_seconds": settings.outbox_poll_interval_seconds,
            },
        )
        await publisher.connect()
        await worker.run(stop_event=stop_event)
    except asyncio.CancelledError:
        logger.info("worker cancelled")
        raise
    finally:
        logger.info("worker shutdown")
        await publisher.close()
        await engine.dispose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
