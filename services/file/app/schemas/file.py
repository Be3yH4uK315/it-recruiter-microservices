from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class FileResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DownloadUrlResponse(BaseModel):
    download_url: str