from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.candidate.entities import CandidateProfile
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


@dataclass(slots=True, frozen=True)
class FileMetadata:
    id: UUID
    owner_service: str
    owner_id: UUID | None
    category: str
    status: str
    filename: str
    content_type: str
    size_bytes: int | None


@dataclass(slots=True, frozen=True)
class AuthVerifiedSubject:
    user_id: UUID
    telegram_id: int
    role: str
    roles: tuple[str, ...]
    is_active: bool
    expires_at: datetime


class OutboxPort(ABC):
    @abstractmethod
    async def publish(self, *, routing_key: str, payload: dict) -> None:
        raise NotImplementedError


class AuthGateway(ABC):
    @abstractmethod
    async def verify_access_token(
        self,
        *,
        access_token: str,
    ) -> AuthVerifiedSubject:
        raise NotImplementedError


class EmployerGateway(ABC):
    @abstractmethod
    async def has_contact_access(
        self,
        *,
        candidate_id: UUID,
        employer_telegram_id: int,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def get_candidate_statistics(
        self,
        *,
        candidate_id: UUID,
    ) -> dict[str, int | bool]:
        raise NotImplementedError


class FileGateway(ABC):
    @abstractmethod
    async def get_avatar_upload_url(
        self,
        *,
        owner_id: UUID,
        filename: str,
        content_type: str,
    ) -> UploadUrlResult:
        raise NotImplementedError

    @abstractmethod
    async def get_resume_upload_url(
        self,
        *,
        owner_id: UUID,
        filename: str,
        content_type: str,
    ) -> UploadUrlResult:
        raise NotImplementedError

    @abstractmethod
    async def get_file_metadata(
        self,
        *,
        file_id: UUID,
    ) -> FileMetadata:
        raise NotImplementedError

    @abstractmethod
    async def complete_file_upload(
        self,
        *,
        file_id: UUID,
    ) -> FileMetadata:
        raise NotImplementedError

    @abstractmethod
    async def cleanup_file(
        self,
        *,
        file_id: UUID,
        reason: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_file_download_url(
        self,
        *,
        file_id: UUID,
        owner_id: UUID,
    ) -> DownloadUrlResult:
        raise NotImplementedError


class EventMapper(ABC):
    @abstractmethod
    def map_domain_event(
        self,
        *,
        event: DomainEvent,
        candidate: CandidateProfile,
    ) -> list[tuple[str, dict]]:
        raise NotImplementedError
