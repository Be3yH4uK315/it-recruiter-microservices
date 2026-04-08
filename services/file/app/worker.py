from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable

from app.application.files.commands.cleanup_file import CleanupFileHandler
from app.application.files.commands.cleanup_stale_pending_files import (
    CleanupStalePendingFilesCommand,
    CleanupStalePendingFilesHandler,
)
from app.config import get_settings
from app.infrastructure.db.session import SessionFactory, engine
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.integrations.s3_client import S3ObjectStorage
from app.infrastructure.messaging.consumer import CleanupRequestedConsumer
from app.infrastructure.messaging.outbox_worker import OutboxWorker
from app.infrastructure.messaging.publisher import EventPublisher
from app.infrastructure.observability.logger import configure_logging, get_logger

logger = get_logger(__name__)


class WorkerSqlAlchemyUnitOfWork(SqlAlchemyUnitOfWork):
    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await super().__aexit__(exc_type, exc, tb)
        finally:
            await self._session.close()


async def _run_stale_pending_cleanup_loop(
    *,
    stop_event: asyncio.Event,
    handler_factory: Callable[[], CleanupStalePendingFilesHandler],
    older_than_seconds: int,
    batch_size: int,
    poll_interval_seconds: float,
) -> None:
    while not stop_event.is_set():
        try:
            handler = handler_factory()
            await handler(
                CleanupStalePendingFilesCommand(
                    older_than_seconds=older_than_seconds,
                    limit=batch_size,
                    reason="pending_upload_expired",
                )
            )
        except Exception:
            logger.exception("stale pending cleanup loop failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval_seconds)
        except asyncio.TimeoutError:
            continue


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)

    storage = S3ObjectStorage(settings)

    publisher = EventPublisher(
        amqp_url=settings.rabbitmq_url,
        exchange_name=settings.rabbitmq_exchange,
    )
    outbox_worker = OutboxWorker(
        session_factory=SessionFactory,
        publisher=publisher,
        batch_size=settings.outbox_batch_size,
        poll_interval_seconds=settings.outbox_poll_interval_seconds,
        max_retries=settings.outbox_max_retries,
    )

    def cleanup_handler_factory() -> CleanupFileHandler:
        def uow_factory() -> WorkerSqlAlchemyUnitOfWork:
            session = SessionFactory()
            return WorkerSqlAlchemyUnitOfWork(session)

        return CleanupFileHandler(
            uow_factory=uow_factory,
            storage=storage,
        )

    def stale_pending_cleanup_handler_factory() -> CleanupStalePendingFilesHandler:
        def uow_factory() -> WorkerSqlAlchemyUnitOfWork:
            session = SessionFactory()
            return WorkerSqlAlchemyUnitOfWork(session)

        return CleanupStalePendingFilesHandler(
            uow_factory=uow_factory,
            storage=storage,
        )

    cleanup_consumer = CleanupRequestedConsumer(
        amqp_url=settings.rabbitmq_url,
        exchange_name=settings.rabbitmq_exchange,
        queue_name=settings.rabbitmq_cleanup_queue,
        routing_key=settings.rabbitmq_cleanup_routing_key,
        cleanup_handler_factory=cleanup_handler_factory,
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
                "cleanup_queue": settings.rabbitmq_cleanup_queue,
                "outbox_batch_size": settings.outbox_batch_size,
                "pending_upload_ttl_seconds": settings.pending_upload_ttl_seconds,
                "pending_cleanup_batch_size": settings.pending_cleanup_batch_size,
            },
        )
        await storage.ensure_bucket_exists()
        await publisher.connect()

        await asyncio.gather(
            outbox_worker.run(stop_event=stop_event),
            cleanup_consumer.run(stop_event=stop_event),
            _run_stale_pending_cleanup_loop(
                stop_event=stop_event,
                handler_factory=stale_pending_cleanup_handler_factory,
                older_than_seconds=settings.pending_upload_ttl_seconds,
                batch_size=settings.pending_cleanup_batch_size,
                poll_interval_seconds=settings.pending_cleanup_poll_interval_seconds,
            ),
        )
    except asyncio.CancelledError:
        logger.info("worker cancelled")
        raise
    finally:
        logger.info("worker shutdown")
        await cleanup_consumer.close()
        await publisher.close()
        await engine.dispose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
