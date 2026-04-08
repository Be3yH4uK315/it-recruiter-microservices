from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import DownloadUrlResult, ObjectStorage
from app.application.common.exceptions import AccessDeniedError, ValidationApplicationError
from app.application.common.uow import UnitOfWork
from app.config import Settings
from app.domain.file.enums import FileStatus
from app.domain.file.errors import FileAccessDeniedError, FileNotFoundError


@dataclass(slots=True, frozen=True)
class CreateDownloadUrlCommand:
    file_id: UUID
    owner_service: str
    owner_id: UUID | None


class CreateDownloadUrlHandler:
    def __init__(
        self,
        *,
        uow_factory: Callable[[], UnitOfWork],
        storage: ObjectStorage,
        settings: Settings,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage
        self._settings = settings

    async def __call__(self, command: CreateDownloadUrlCommand) -> DownloadUrlResult:
        owner_service = command.owner_service.strip()
        if not owner_service:
            raise ValidationApplicationError("owner_service is required")

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

            if file.status == FileStatus.DELETED:
                raise FileNotFoundError("file not found")

            if file.status != FileStatus.ACTIVE:
                raise ValidationApplicationError("file is not uploaded yet")

            file_id = file.id
            object_key = file.object_key

        download_url = await self._storage.generate_presigned_download_url(
            object_key=object_key,
            expires_in=self._settings.default_download_url_expiration_seconds,
        )

        return DownloadUrlResult(
            file_id=file_id,
            download_url=download_url,
            method="GET",
            expires_in=self._settings.default_download_url_expiration_seconds,
        )
