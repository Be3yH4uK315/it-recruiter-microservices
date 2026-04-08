from __future__ import annotations

import asyncio
import signal

from app.config import get_settings
from app.infrastructure.integrations.http_client import build_default_async_http_client
from app.infrastructure.messaging.candidate_events_consumer import CandidateEventsConsumer
from app.infrastructure.observability.logger import configure_logging, get_logger
from app.infrastructure.observability.telemetry import init_telemetry


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger(__name__)

    init_telemetry(
        service_name=settings.app_name,
        service_version=settings.app_version,
        environment=settings.app_env,
    )

    http_client = build_default_async_http_client(settings)
    consumer = CandidateEventsConsumer(
        settings=settings,
        http_client=http_client,
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
            pass

    logger.info(
        "worker startup",
        extra={
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "environment": settings.app_env,
        },
    )

    try:
        await consumer.run_forever(stop_event=stop_event)
    finally:
        logger.info("worker shutdown")
        await http_client.aclose()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
