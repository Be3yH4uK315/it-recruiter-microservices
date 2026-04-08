from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.application.common.contracts import ObjectStorage
from app.application.common.event_dispatch import dispatch_file_events
from app.application.common.uow import UnitOfWork
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class CleanupStalePendingFilesCommand:
    older_than_seconds: int
    limit: int = 100
    reason: str = "pending_upload_expired"


@dataclass(slots=True, frozen=True)
class CleanupStalePendingFilesResult:
    scanned: int
    cleaned: int


class CleanupStalePendingFilesHandler:
    def __init__(
        self,
        *,
        uow_factory: Callable[[], UnitOfWork],
        storage: ObjectStorage,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def __call__(
        self,
        command: CleanupStalePendingFilesCommand,
    ) -> CleanupStalePendingFilesResult:
        now = datetime.now(timezone.utc)
        created_before = now - timedelta(seconds=max(1, command.older_than_seconds))
        limit = max(1, command.limit)

        stale_object_keys: list[tuple[str, str]] = []

        async with self._uow_factory() as uow:
            stale_files = await uow.files.list_stale_pending(
                created_before=created_before,
                limit=limit,
            )

            if not stale_files:
                return CleanupStalePendingFilesResult(scanned=0, cleaned=0)

            cleaned = 0

            for file in stale_files:
                try:
                    file.mark_deleted(reason=command.reason)
                    await uow.files.save(file)
                    await dispatch_file_events(uow=uow, file=file)
                    stale_object_keys.append((str(file.id), file.object_key))
                    cleaned += 1
                except Exception:
                    logger.exception(
                        "failed to mark stale pending file as deleted",
                        extra={
                            "file_id": str(file.id),
                            "object_key": file.object_key,
                        },
                    )

            await uow.flush()

        for file_id, object_key in stale_object_keys:
            try:
                object_exists = await self._storage.object_exists(object_key=object_key)
                if object_exists:
                    await self._storage.delete_object(object_key=object_key)
            except Exception:
                logger.exception(
                    "failed to inspect or delete stale pending object",
                    extra={
                        "file_id": file_id,
                        "object_key": object_key,
                    },
                )

        logger.info(
            "stale pending cleanup finished",
            extra={
                "scanned": len(stale_object_keys),
                "cleaned": cleaned,
                "created_before": created_before.isoformat(),
            },
        )

        return CleanupStalePendingFilesResult(
            scanned=len(stale_files),
            cleaned=cleaned,
        )
