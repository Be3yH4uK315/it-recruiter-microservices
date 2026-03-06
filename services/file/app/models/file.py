import uuid

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.db import Base


class FileRecord(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_telegram_id = Column(BigInteger, index=True, nullable=False)

    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    s3_key = Column(String(500), unique=True, nullable=False)
    bucket = Column(String(100), nullable=False)
    file_type = Column(String(50), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
