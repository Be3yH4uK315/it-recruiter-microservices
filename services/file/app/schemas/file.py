from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FileTypeEnum(str, Enum):
    AVATAR = "avatar"
    RESUME = "resume"
    DOCUMENT = "document"


class FileResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DownloadUrlResponse(BaseModel):
    download_url: str


class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str


class UploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int
