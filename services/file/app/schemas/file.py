from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.application.common.contracts import DownloadUrlResult, UploadUrlResult
from app.application.files.dto.views import FileView
from app.domain.file.enums import FileCategory, FileStatus


class CreateUploadUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_service: str
    owner_id: UUID | None = None
    filename: str
    content_type: str
    category: FileCategory

    @field_validator("owner_service", "filename", "content_type")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized


class CreateUploadUrlResponse(BaseModel):
    file_id: UUID
    upload_url: str
    method: str
    expires_in: int
    headers: dict[str, str]

    @classmethod
    def from_result(cls, result: UploadUrlResult) -> "CreateUploadUrlResponse":
        return cls(
            file_id=result.file_id,
            upload_url=result.upload_url,
            method=result.method,
            expires_in=result.expires_in,
            headers=result.headers,
        )


class CreateDownloadUrlResponse(BaseModel):
    file_id: UUID
    download_url: str
    method: str
    expires_in: int

    @classmethod
    def from_result(cls, result: DownloadUrlResult) -> "CreateDownloadUrlResponse":
        return cls(
            file_id=result.file_id,
            download_url=result.download_url,
            method=result.method,
            expires_in=result.expires_in,
        )


class FileResponse(BaseModel):
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
    def from_view(cls, view: FileView) -> "FileResponse":
        return cls(
            id=view.id,
            owner_service=view.owner_service,
            owner_id=view.owner_id,
            category=view.category,
            filename=view.filename,
            content_type=view.content_type,
            bucket=view.bucket,
            object_key=view.object_key,
            status=view.status,
            size_bytes=view.size_bytes,
            created_at=view.created_at,
            updated_at=view.updated_at,
            deleted_at=view.deleted_at,
        )


class DeleteFileResponse(BaseModel):
    status: str = "deleted"


class RegisterUploadedFileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    size_bytes: int | None = Field(default=None, ge=0)


class CleanupFileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    requested_by_service: str

    @field_validator("reason", "requested_by_service")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized
