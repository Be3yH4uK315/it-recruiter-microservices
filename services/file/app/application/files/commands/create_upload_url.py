from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.application.common.contracts import ObjectStorage, UploadUrlResult
from app.application.common.event_dispatch import dispatch_file_events
from app.application.common.exceptions import ValidationApplicationError
from app.application.common.uow import UnitOfWork
from app.config import Settings
from app.domain.file.entities import StoredFile
from app.domain.file.enums import FileCategory

_ALLOWED_CATEGORIES_BY_OWNER_SERVICE: dict[str, set[FileCategory]] = {
    "candidate-service": {
        FileCategory.CANDIDATE_AVATAR,
        FileCategory.CANDIDATE_RESUME,
    },
    "employer-service": {
        FileCategory.EMPLOYER_AVATAR,
        FileCategory.EMPLOYER_DOCUMENT,
    },
}


@dataclass(slots=True, frozen=True)
class CreateUploadUrlCommand:
    owner_service: str
    owner_id: UUID | None
    filename: str
    content_type: str
    category: FileCategory


class CreateUploadUrlHandler:
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

    async def __call__(self, command: CreateUploadUrlCommand) -> UploadUrlResult:
        (
            normalized_owner_service,
            normalized_owner_id,
            normalized_filename,
            normalized_content_type,
        ) = self._validate(command)

        file_id = uuid4()
        object_key = self._build_object_key(
            file_id=file_id,
            owner_service=normalized_owner_service,
            owner_id=normalized_owner_id,
            category=command.category,
            filename=normalized_filename,
        )

        if len(object_key) > self._settings.max_object_key_length:
            raise ValidationApplicationError("object_key exceeds maximum length")

        file = StoredFile.create_pending(
            file_id=file_id,
            owner_service=normalized_owner_service,
            owner_id=normalized_owner_id,
            category=command.category,
            filename=normalized_filename,
            content_type=normalized_content_type,
            bucket=self._settings.s3_bucket_name,
            object_key=object_key,
        )

        async with self._uow_factory() as uow:
            await uow.files.add(file)
            await dispatch_file_events(uow=uow, file=file)
            await uow.flush()

        upload_url = await self._storage.generate_presigned_upload_url(
            object_key=file.object_key,
            content_type=file.content_type,
            expires_in=self._settings.default_upload_url_expiration_seconds,
        )

        return UploadUrlResult(
            file_id=file.id,
            upload_url=upload_url,
            method="PUT",
            expires_in=self._settings.default_upload_url_expiration_seconds,
            headers={"Content-Type": file.content_type},
        )

    def _validate(
        self,
        command: CreateUploadUrlCommand,
    ) -> tuple[str, UUID, str, str]:
        owner_service = command.owner_service.strip()
        filename = command.filename.strip()
        content_type = command.content_type.strip().lower()

        if not owner_service:
            raise ValidationApplicationError("owner_service is required")

        if owner_service not in _ALLOWED_CATEGORIES_BY_OWNER_SERVICE:
            raise ValidationApplicationError("owner_service is not supported")

        if command.category not in _ALLOWED_CATEGORIES_BY_OWNER_SERVICE[owner_service]:
            raise ValidationApplicationError("category is not allowed for owner_service")

        if command.owner_id is None:
            raise ValidationApplicationError("owner_id is required")

        if not filename:
            raise ValidationApplicationError("filename is required")

        if len(filename) > self._settings.max_filename_length:
            raise ValidationApplicationError("filename exceeds maximum length")

        if not content_type:
            raise ValidationApplicationError("content_type is required")

        if len(content_type) > self._settings.max_content_type_length:
            raise ValidationApplicationError("content_type exceeds maximum length")

        if (
            command.category
            in {
                FileCategory.CANDIDATE_AVATAR,
                FileCategory.EMPLOYER_AVATAR,
            }
            and content_type not in self._settings.allowed_image_content_types
        ):
            raise ValidationApplicationError("invalid content_type for avatar")

        if (
            command.category
            in {
                FileCategory.CANDIDATE_RESUME,
                FileCategory.EMPLOYER_DOCUMENT,
            }
            and content_type not in self._settings.allowed_resume_content_types
        ):
            raise ValidationApplicationError("invalid content_type for document")

        return owner_service, command.owner_id, filename, content_type

    @staticmethod
    def _build_object_key(
        *,
        file_id: UUID,
        owner_service: str,
        owner_id: UUID,
        category: FileCategory,
        filename: str,
    ) -> str:
        safe_filename = filename.strip().replace("/", "_").replace("\\", "_")
        return f"{owner_service}/{category.value}/{owner_id}/{file_id}/{safe_filename}"
