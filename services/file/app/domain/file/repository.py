from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.file.entities import StoredFile


class FileRepository(ABC):
    @abstractmethod
    async def add(self, file: StoredFile) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, file_id: UUID) -> StoredFile | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_object_key(self, object_key: str) -> StoredFile | None:
        raise NotImplementedError

    @abstractmethod
    async def save(self, file: StoredFile) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, file: StoredFile) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_stale_pending(
        self,
        *,
        created_before: datetime,
        limit: int,
    ) -> list[StoredFile]:
        raise NotImplementedError
