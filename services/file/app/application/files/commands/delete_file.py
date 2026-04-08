from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import ObjectStorage
from app.application.common.event_dispatch import dispatch_file_events
from app.application.common.exceptions import AccessDeniedError, ValidationApplicationError
from app.application.common.uow import UnitOfWork
from app.domain.file.errors import FileAccessDeniedError, FileNotFoundError
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class DeleteFileCommand:
    file_id: UUID
    owner_service: str
    owner_id: UUID | None
    reason: str = "deleted_by_owner"


class DeleteFileHandler:
    def __init__(
        self,
        *,
        uow_factory: Callable[[], UnitOfWork],
        storage: ObjectStorage,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def __call__(self, command: DeleteFileCommand) -> None:
        owner_service = command.owner_service.strip()
        if not owner_service:
            raise ValidationApplicationError("owner_service is required")

        object_key_to_delete: str | None = None

        async with self._uow_factory() as uow:
            file = await uow.files.get_by_id(command.file_id)
            if file is None:
                raise FileNotFoundError("file not found")

            try:
                file.ensure_access(
                    owner_service=owner_service,
                    owner_id=command.owner_id,
                )
            except FileAccessDeniedError as exc:
                raise AccessDeniedError(str(exc)) from exc

            if file.is_deleted():
                return

            file.mark_deleted(reason=command.reason)
            object_key_to_delete = file.object_key

            await uow.files.save(file)
            await dispatch_file_events(uow=uow, file=file)
            await uow.flush()

        if object_key_to_delete is not None:
            try:
                await self._storage.delete_object(object_key=object_key_to_delete)
            except Exception:
                logger.exception(
                    "failed to physically delete object after file was marked deleted",
                    extra={
                        "file_id": str(command.file_id),
                        "object_key": object_key_to_delete,
                        "owner_service": owner_service,
                    },
                )
