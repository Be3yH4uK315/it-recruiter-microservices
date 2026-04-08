from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.file.entities import StoredFile
from app.domain.file.enums import FileStatus
from app.domain.file.errors import FileNotFoundError
from app.domain.file.repository import FileRepository
from app.domain.file.value_objects import FileOwnership
from app.infrastructure.db.models.file import FileModel


class SqlAlchemyFileRepository(FileRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, file: StoredFile) -> None:
        self._session.add(self._to_orm(file))

    async def get_by_id(self, file_id: UUID) -> StoredFile | None:
        stmt = select(FileModel).where(FileModel.id == file_id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            return None
        return self._to_domain(orm_obj)

    async def get_by_object_key(self, object_key: str) -> StoredFile | None:
        stmt = select(FileModel).where(FileModel.object_key == object_key)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            return None
        return self._to_domain(orm_obj)

    async def save(self, file: StoredFile) -> None:
        stmt = select(FileModel).where(FileModel.id == file.id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            raise FileNotFoundError(f"file {file.id} not found")

        orm_obj.owner_service = file.owner.owner_service
        orm_obj.owner_id = file.owner.owner_id
        orm_obj.category = file.category
        orm_obj.filename = file.filename
        orm_obj.content_type = file.content_type
        orm_obj.bucket = file.bucket
        orm_obj.object_key = file.object_key
        orm_obj.status = file.status
        orm_obj.size_bytes = file.size_bytes
        orm_obj.created_at = self._normalize_datetime(file.created_at)
        orm_obj.updated_at = self._normalize_datetime(file.updated_at)
        orm_obj.deleted_at = self._normalize_datetime_or_none(file.deleted_at)

    async def delete(self, file: StoredFile) -> None:
        stmt = select(FileModel).where(FileModel.id == file.id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            raise FileNotFoundError(f"file {file.id} not found")

        await self._session.delete(orm_obj)

    async def list_stale_pending(
        self,
        *,
        created_before: datetime,
        limit: int,
    ) -> list[StoredFile]:
        stmt = (
            select(FileModel)
            .where(
                FileModel.status == FileStatus.PENDING_UPLOAD,
                FileModel.created_at < self._normalize_datetime(created_before),
            )
            .order_by(FileModel.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(item) for item in result.scalars().all()]

    @classmethod
    def _to_domain(cls, model: FileModel) -> StoredFile:
        return StoredFile(
            id=model.id,
            owner=FileOwnership(
                owner_service=model.owner_service,
                owner_id=model.owner_id,
            ),
            category=model.category,
            filename=model.filename,
            content_type=model.content_type,
            bucket=model.bucket,
            object_key=model.object_key,
            status=model.status,
            size_bytes=model.size_bytes,
            created_at=cls._normalize_datetime(model.created_at),
            updated_at=cls._normalize_datetime(model.updated_at),
            deleted_at=cls._normalize_datetime_or_none(model.deleted_at),
        )

    @classmethod
    def _to_orm(cls, file: StoredFile) -> FileModel:
        return FileModel(
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
            created_at=cls._normalize_datetime(file.created_at),
            updated_at=cls._normalize_datetime(file.updated_at),
            deleted_at=cls._normalize_datetime_or_none(file.deleted_at),
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _normalize_datetime_or_none(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
