from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.file.enums import FileCategory


@dataclass(slots=True, frozen=True)
class FileOwnership:
    owner_service: str
    owner_id: UUID | None

    def __post_init__(self) -> None:
        normalized_owner_service = self.owner_service.strip()
        if not normalized_owner_service:
            raise ValueError("owner_service must not be empty")

        object.__setattr__(self, "owner_service", normalized_owner_service)

    def matches(
        self,
        *,
        owner_service: str,
        owner_id: UUID | None,
    ) -> bool:
        return self.owner_service == owner_service and self.owner_id == owner_id


@dataclass(slots=True, frozen=True)
class FileDescriptor:
    filename: str
    content_type: str
    category: FileCategory

    def __post_init__(self) -> None:
        normalized_filename = self.filename.strip()
        normalized_content_type = self.content_type.strip().lower()

        if not normalized_filename:
            raise ValueError("filename must not be empty")
        if not normalized_content_type:
            raise ValueError("content_type must not be empty")

        object.__setattr__(self, "filename", normalized_filename)
        object.__setattr__(self, "content_type", normalized_content_type)
