from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.common.events import DomainEvent
from app.domain.file.enums import FileCategory, FileStatus
from app.domain.file.errors import (
    FileAccessDeniedError,
    FileAlreadyDeletedError,
    InvalidFileStateError,
)
from app.domain.file.value_objects import FileOwnership


@dataclass(slots=True, frozen=True)
class FileCreated(DomainEvent):
    file_id: UUID | None = None
    owner_service: str | None = None
    owner_id: UUID | None = None
    category: str | None = None
    object_key: str | None = None


@dataclass(slots=True, frozen=True)
class FileActivated(DomainEvent):
    file_id: UUID | None = None
    object_key: str | None = None


@dataclass(slots=True, frozen=True)
class FileDeleted(DomainEvent):
    file_id: UUID | None = None
    owner_service: str | None = None
    owner_id: UUID | None = None
    category: str | None = None
    object_key: str | None = None
    reason: str | None = None


@dataclass(slots=True)
class StoredFile:
    id: UUID
    owner: FileOwnership
    category: FileCategory
    filename: str
    content_type: str
    bucket: str
    object_key: str
    status: FileStatus
    size_bytes: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def create_pending(
        cls,
        *,
        owner_service: str,
        owner_id: UUID | None,
        category: FileCategory,
        filename: str,
        content_type: str,
        bucket: str,
        object_key: str,
        file_id: UUID | None = None,
    ) -> "StoredFile":
        now = datetime.now(timezone.utc)

        file = cls(
            id=file_id or uuid4(),
            owner=FileOwnership(
                owner_service=owner_service,
                owner_id=owner_id,
            ),
            category=category,
            filename=filename.strip(),
            content_type=content_type.strip().lower(),
            bucket=bucket.strip(),
            object_key=object_key.strip(),
            status=FileStatus.PENDING_UPLOAD,
            created_at=now,
            updated_at=now,
        )

        file._events.append(
            FileCreated(
                file_id=file.id,
                owner_service=file.owner.owner_service,
                owner_id=file.owner.owner_id,
                category=file.category.value,
                object_key=file.object_key,
            )
        )
        return file

    def activate(self, *, size_bytes: int | None = None) -> None:
        if self.status == FileStatus.DELETED:
            raise InvalidFileStateError("file is deleted")

        if size_bytes is not None and size_bytes < 0:
            raise InvalidFileStateError("file size must be >= 0")

        if self.status == FileStatus.ACTIVE:
            if size_bytes is not None and self.size_bytes is None:
                self.size_bytes = size_bytes
                self.updated_at = datetime.now(timezone.utc)
            return

        self.status = FileStatus.ACTIVE
        self.size_bytes = size_bytes
        self.updated_at = datetime.now(timezone.utc)

        self._events.append(
            FileActivated(
                file_id=self.id,
                object_key=self.object_key,
            )
        )

    def ensure_access(
        self,
        *,
        owner_service: str,
        owner_id: UUID | None,
    ) -> None:
        if not self.owner.matches(owner_service=owner_service, owner_id=owner_id):
            raise FileAccessDeniedError("access to file is denied")

    def mark_deleted(self, *, reason: str) -> None:
        if self.status == FileStatus.DELETED:
            raise FileAlreadyDeletedError("file is already deleted")

        normalized_reason = reason.strip()
        if not normalized_reason:
            raise InvalidFileStateError("delete reason must not be empty")

        self.status = FileStatus.DELETED
        self.deleted_at = datetime.now(timezone.utc)
        self.updated_at = self.deleted_at

        self._events.append(
            FileDeleted(
                file_id=self.id,
                owner_service=self.owner.owner_service,
                owner_id=self.owner.owner_id,
                category=self.category.value,
                object_key=self.object_key,
                reason=normalized_reason,
            )
        )

    def is_active(self) -> bool:
        return self.status == FileStatus.ACTIVE

    def is_deleted(self) -> bool:
        return self.status == FileStatus.DELETED

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events
