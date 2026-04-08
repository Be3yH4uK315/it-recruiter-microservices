from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import ObjectStorage
from app.application.common.event_dispatch import dispatch_file_events
from app.application.common.exceptions import ValidationApplicationError
from app.application.common.uow import UnitOfWork
from app.domain.file.errors import FileNotFoundError


@dataclass(slots=True, frozen=True)
class RegisterUploadedFileCommand:
    file_id: UUID
    size_bytes: int | None = None


class RegisterUploadedFileHandler:
    def __init__(
        self,
        *,
        uow_factory: Callable[[], UnitOfWork],
        storage: ObjectStorage,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def __call__(self, command: RegisterUploadedFileCommand) -> None:
        async with self._uow_factory() as uow:
            file = await uow.files.get_by_id(command.file_id)
            if file is None or file.is_deleted():
                raise FileNotFoundError("file not found")

            if file.is_active():
                return

            object_key = file.object_key

        stored_size = await self._storage.get_object_size(object_key=object_key)
        if stored_size is None:
            raise ValidationApplicationError("file object was not uploaded")

        actual_size = command.size_bytes if command.size_bytes is not None else stored_size

        async with self._uow_factory() as uow:
            file = await uow.files.get_by_id(command.file_id)
            if file is None or file.is_deleted():
                raise FileNotFoundError("file not found")

            if file.is_active():
                return

            file.activate(size_bytes=actual_size)

            await uow.files.save(file)
            await dispatch_file_events(uow=uow, file=file)
            await uow.flush()
