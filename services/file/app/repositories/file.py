from uuid import UUID
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import FileRecord

class FileRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, file_record: FileRecord) -> FileRecord:
        self.session.add(file_record)
        return file_record

    async def get_by_id(self, file_id: UUID) -> Optional[FileRecord]:
        query = select(FileRecord).where(FileRecord.id == file_id)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def delete(self, file_record: FileRecord):
        await self.session.delete(file_record)