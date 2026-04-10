from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.common.events import DomainEvent
from app.domain.employer.entities import ContactRequest, EmployerProfile, SearchSession


@dataclass(slots=True, frozen=True)
class AuthVerifiedSubject:
    user_id: UUID
    telegram_id: int
    role: str
    roles: tuple[str, ...]
    is_active: bool
    expires_at: datetime


@dataclass(slots=True, frozen=True)
class UploadUrlResult:
    file_id: UUID
    upload_url: str
    method: str
    expires_in: int
    headers: dict[str, str]


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
class FileDownloadResult:
    file_id: UUID
    download_url: str
    method: str
    expires_in: int


@dataclass(slots=True, frozen=True)
class CandidateShortProfile:
    id: UUID
    display_name: str
    headline_role: str
    location: str | None = None
    work_modes: list[str] = field(default_factory=list)
    experience_years: float = 0.0

    contacts_visibility: str | None = None
    contacts: dict[str, str | None] | None = None
    can_view_contacts: bool = False

    status: str | None = None
    english_level: str | None = None
    about_me: str | None = None

    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None

    skills: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    experiences: list[dict[str, Any]] = field(default_factory=list)
    projects: list[dict[str, Any]] = field(default_factory=list)

    avatar_file_id: UUID | None = None
    avatar_download_url: str | None = None
    resume_file_id: UUID | None = None
    resume_download_url: str | None = None

    created_at: str | None = None
    updated_at: str | None = None
    version_id: int | None = None

    explanation: dict[str, Any] | None = None
    match_score: float = 0.0


@dataclass(slots=True, frozen=True)
class SearchCandidateResult:
    candidate_id: UUID
    display_name: str
    headline_role: str
    experience_years: float
    location: str | None = None
    skills: list[dict[str, Any] | str] = field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    english_level: str | None = None
    about_me: str | None = None
    match_score: float = 0.0
    explanation: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class SearchCandidatesBatchResult:
    total: int
    items: list[SearchCandidateResult] = field(default_factory=list)
    is_degraded: bool = False


class OutboxPort(ABC):
    @abstractmethod
    async def publish(self, *, routing_key: str, payload: dict) -> None:
        raise NotImplementedError


class EventMapper(ABC):
    @abstractmethod
    def map_domain_event(
        self,
        *,
        event: DomainEvent,
        employer: EmployerProfile | None = None,
        search_session: SearchSession | None = None,
        contact_request: ContactRequest | None = None,
    ) -> list[tuple[str, dict]]:
        raise NotImplementedError


class EventPublisher(ABC):
    @abstractmethod
    async def publish(
        self,
        *,
        routing_key: str,
        payload: dict,
    ) -> None:
        raise NotImplementedError


class AuthGateway(ABC):
    @abstractmethod
    async def verify_access_token(
        self,
        *,
        access_token: str,
    ) -> AuthVerifiedSubject:
        raise NotImplementedError


@dataclass(slots=True, frozen=True)
class CandidateIdentity:
    candidate_id: UUID
    telegram_id: int
    status: str | None = None


class CandidateGateway(ABC):
    @abstractmethod
    async def get_candidate_profile(
        self,
        *,
        candidate_id: UUID,
        employer_telegram_id: int,
    ) -> CandidateShortProfile | None:
        raise NotImplementedError

    @abstractmethod
    async def get_candidate_identity(
        self,
        *,
        telegram_id: int,
    ) -> CandidateIdentity | None:
        raise NotImplementedError


class FileGateway(ABC):
    @abstractmethod
    async def get_employer_avatar_upload_url(
        self,
        *,
        owner_id: UUID,
        filename: str,
        content_type: str,
    ) -> UploadUrlResult:
        raise NotImplementedError

    @abstractmethod
    async def get_employer_document_upload_url(
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
    async def get_download_url(
        self,
        *,
        file_id: UUID,
        owner_id: UUID,
    ) -> FileDownloadResult:
        raise NotImplementedError


class SearchGateway(ABC):
    @abstractmethod
    async def search_candidates(
        self,
        *,
        filters: dict,
        limit: int,
        include_total: bool = True,
    ) -> SearchCandidatesBatchResult:
        raise NotImplementedError
