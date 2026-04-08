from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from app.domain.common.events import DomainEvent


@dataclass(slots=True, frozen=True)
class UploadUrlResult:
    file_id: UUID
    upload_url: str
    method: str
    expires_in: int
    headers: dict[str, str]


@dataclass(slots=True, frozen=True)
class DownloadUrlResult:
    file_id: UUID
    download_url: str
    method: str
    expires_in: int


class ObjectStorage(ABC):
    @abstractmethod
    async def ensure_bucket_exists(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def generate_presigned_upload_url(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_in: int,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate_presigned_download_url(
        self,
        *,
        object_key: str,
        expires_in: int,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def delete_object(self, *, object_key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def object_exists(self, *, object_key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def get_object_size(self, *, object_key: str) -> int | None:
        raise NotImplementedError


class EventMapper(ABC):
    @abstractmethod
    def map_domain_event(
        self,
        *,
        event: DomainEvent,
    ) -> list[tuple[str, dict]]:
        raise NotImplementedError


class OutboxPort(ABC):
    @abstractmethod
    async def publish(self, *, routing_key: str, payload: dict) -> None:
        raise NotImplementedError
