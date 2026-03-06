import uuid

import structlog
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.file import FileRecord
from app.repositories.file import FileRepository
from app.services.s3_client import s3_service

logger = structlog.get_logger()


class FileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = FileRepository(db)

    async def upload_file(
        self, file: UploadFile, owner_telegram_id: int, file_type: str
    ) -> FileRecord:
        file_ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
        unique_id = uuid.uuid4()
        s3_key = f"{file_type}s/{owner_telegram_id}/{unique_id}.{file_ext}"

        try:
            await s3_service.upload_fileobj(
                file_obj=file.file,
                object_key=s3_key,
                content_type=file.content_type or "application/octet-stream",
            )
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            raise HTTPException(status_code=502, detail="Failed to upload file to storage")

        file.file.seek(0, 2)
        size_bytes = file.file.tell()

        db_file = FileRecord(
            id=unique_id,
            owner_telegram_id=owner_telegram_id,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=size_bytes,
            s3_key=s3_key,
            bucket=settings.S3_BUCKET_NAME,
            file_type=file_type,
        )

        await self.repo.create(db_file)
        await self.db.commit()
        await self.db.refresh(db_file)

        return db_file

    async def get_download_url(self, file_id: uuid.UUID) -> str | None:
        file_record = await self.repo.get_by_id(file_id)
        if not file_record:
            return None

        return await s3_service.generate_presigned_url(file_record.s3_key)

    async def delete_file(self, file_id: uuid.UUID, owner_telegram_id: int):
        file_record = await self.repo.get_by_id(file_id)
        if not file_record:
            return

        if file_record.owner_telegram_id != int(owner_telegram_id):
            logger.warning(f"Unauthorized delete attempt. Owner: {file_record.owner_telegram_id}, \
                    Requester: {owner_telegram_id}")
            raise HTTPException(status_code=403, detail="Not file owner")

        try:
            await s3_service.delete_file(file_record.s3_key)
        except Exception as e:
            logger.error(f"S3 delete error: {e}")

        await self.repo.delete(file_record)
        await self.db.commit()
