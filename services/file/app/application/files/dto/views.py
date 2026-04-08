from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.file.entities import StoredFile
from app.domain.file.enums import FileCategory, FileStatus


@dataclass(slots=True, frozen=True)
class FileView:
    id: UUID
    owner_service: str
    owner_id: UUID | None
    category: FileCategory
    filename: str
    content_type: str
    bucket: str
    object_key: str
    status: FileStatus
    size_bytes: int | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_entity(cls, file: StoredFile) -> "FileView":
        return cls(
            id=file.id,
            owner_service=file.owner.owner_service,
            owner_id=file.owner.owner_id,
            category=file.category,
            filename=file.filename,
            content_type=file.content_type,
            bucket=file.bucket,
            object_key=file.object_key,
            status=file.status,
            size_bytes=file.size_bytes,
            created_at=file.created_at,
            updated_at=file.updated_at,
            deleted_at=file.deleted_at,
        )
