from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.files.commands.cleanup_stale_pending_files import (
    CleanupStalePendingFilesCommand,
    CleanupStalePendingFilesHandler,
)
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class PendingUploadCleanupWorker:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        storage,
        ttl_seconds: int,
        batch_size: int,
        poll_interval_seconds: float,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._ttl_seconds = ttl_seconds
        self._batch_size = batch_size
        self._poll_interval_seconds = poll_interval_seconds

    async def run(self, *, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                processed_count = await self._run_once()
                if processed_count > 0:
                    logger.info(
                        "stale pending files cleaned",
                        extra={"processed_count": processed_count},
                    )
            except Exception as exc:
                logger.exception(
                    "pending upload cleanup iteration failed",
                    exc_info=exc,
                )

            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self._poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue

    async def _run_once(self) -> int:
        async with self._session_factory() as session:

            def uow_factory() -> SqlAlchemyUnitOfWork:
                return SqlAlchemyUnitOfWork(session)

            handler = CleanupStalePendingFilesHandler(
                uow_factory=uow_factory,
                storage=self._storage,
            )
            result = await handler(
                CleanupStalePendingFilesCommand(
                    older_than_seconds=self._ttl_seconds,
                    limit=self._batch_size,
                    reason="pending_upload_expired",
                )
            )
            return result.cleaned
