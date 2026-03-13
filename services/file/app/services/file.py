import uuid

import filetype
import structlog
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.file import FileRecord
from app.repositories.file import FileRepository
from app.schemas.file import FileTypeEnum
from app.services.s3_client import s3_service

logger = structlog.get_logger()


class FileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = FileRepository(db)

    async def upload_file(
        self, file: UploadFile, owner_telegram_id: int, file_type: FileTypeEnum
    ) -> FileRecord:
        header_bytes = await file.read(2048)
        await file.seek(0)

        kind = filetype.guess(header_bytes)

        if file_type == FileTypeEnum.AVATAR:
            if kind is None or kind.mime not in ["image/jpeg", "image/png", "image/webp"]:
                raise HTTPException(
                    status_code=415, detail="Invalid image format. Only JPG, PNG, WEBP allowed."
                )
        elif file_type == FileTypeEnum.RESUME:
            mime = kind.mime if kind else None
            allowed_resumes = ["application/pdf", "application/zip", "application/msword"]
            if mime not in allowed_resumes and not file.filename.endswith(".docx"):
                raise HTTPException(
                    status_code=415, detail="Invalid resume format. Only PDF and DOCX allowed."
                )

        file_ext = (
            kind.extension
            if kind
            else (file.filename.split(".")[-1] if "." in file.filename else "bin")
        )
        real_content_type = kind.mime if kind else (file.content_type or "application/octet-stream")

        unique_id = uuid.uuid4()
        s3_key = f"{file_type.value}s/{owner_telegram_id}/{unique_id}.{file_ext}"

        try:
            await s3_service.upload_fileobj(
                file_obj=file.file,
                object_key=s3_key,
                content_type=real_content_type,
            )
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            raise HTTPException(status_code=502, detail="Failed to upload file to storage")

        size_bytes = file.size if getattr(file, "size", None) else 0

        db_file = FileRecord(
            id=unique_id,
            owner_telegram_id=owner_telegram_id,
            filename=file.filename,
            content_type=real_content_type,
            size_bytes=size_bytes,
            s3_key=s3_key,
            bucket=settings.S3_BUCKET_NAME,
            file_type=file_type.value,
        )

        await self.repo.create(db_file)
        await self.db.commit()
        await self.db.refresh(db_file)

        return db_file

    async def generate_upload_url(
        self, owner_id: str, filename: str, content_type: str, file_type: FileTypeEnum
    ) -> dict:
        file_ext = filename.split(".")[-1] if "." in filename else "bin"
        unique_id = uuid.uuid4()
        s3_key = f"{file_type.value}s/{owner_id}/{unique_id}.{file_ext}"

        url = await s3_service.generate_presigned_url(
            object_key=s3_key,
            client_method="put_object",
            expiration=3600,
            content_type=content_type,
        )

        if not url:
            raise HTTPException(status_code=502, detail="Could not generate upload URL")

        return {"upload_url": url, "object_key": s3_key, "expires_in": 3600}

    async def get_download_url(self, file_id: uuid.UUID) -> str | None:
        file_record = await self.repo.get_by_id(file_id)
        if not file_record:
            return None

        return await s3_service.generate_presigned_url(
            file_record.s3_key, client_method="get_object"
        )

    async def delete_file(self, file_id: uuid.UUID, owner_telegram_id: int):
        file_record = await self.repo.get_by_id(file_id)
        if not file_record:
            return

        if file_record.owner_telegram_id != int(owner_telegram_id):
            raise HTTPException(status_code=403, detail="Not file owner")

        try:
            await s3_service.delete_file(file_record.s3_key)
        except Exception as e:
            logger.error(f"S3 delete error: {e}")
            if "404" not in str(e):
                raise HTTPException(status_code=502, detail="Storage unavailable, try again later")

        await self.repo.delete(file_record)
        await self.db.commit()
