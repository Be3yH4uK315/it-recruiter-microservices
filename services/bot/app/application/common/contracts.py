from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class _UnsetType:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET = _UnsetType()


@dataclass(slots=True, frozen=True)
class AuthUserView:
    id: UUID
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    role: str
    roles: tuple[str, ...]
    is_active: bool


@dataclass(slots=True, frozen=True)
class AuthSessionView:
    user: AuthUserView
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


@dataclass(slots=True, frozen=True)
class AuthVerifiedSubject:
    user_id: UUID
    telegram_id: int
    role: str
    roles: tuple[str, ...]
    is_active: bool
    expires_at: datetime


@dataclass(slots=True, frozen=True)
class CallbackContextView:
    token: str
    action_type: str
    payload: dict


@dataclass(slots=True, frozen=True)
class CandidateProfileSummary:
    id: UUID
    telegram_id: int | None
    display_name: str
    headline_role: str
    location: str | None
    status: str | None
    avatar_file_id: UUID | None
    avatar_download_url: str | None
    resume_file_id: UUID | None
    resume_download_url: str | None
    version_id: int | None
    experience_years: float = 0.0
    work_modes: list[str] | None = None
    contacts_visibility: str | None = None
    contacts: dict[str, str | None] | None = None
    can_view_contacts: bool = False
    english_level: str | None = None
    about_me: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    skills: list[dict] | None = None
    education: list[dict] | None = None
    experiences: list[dict] | None = None
    projects: list[dict] | None = None
    explanation: dict | None = None
    match_score: float = 0.0


@dataclass(slots=True, frozen=True)
class CandidateStatisticsView:
    total_views: int
    total_likes: int
    total_contact_requests: int
    is_degraded: bool = False


@dataclass(slots=True, frozen=True)
class EmployerProfileSummary:
    id: UUID
    telegram_id: int
    company: str | None
    avatar_file_id: UUID | None
    avatar_download_url: str | None
    document_file_id: UUID | None
    document_download_url: str | None
    contacts: dict[str, str | None] | None = None


@dataclass(slots=True, frozen=True)
class EmployerStatisticsView:
    total_viewed: int
    total_liked: int
    total_contact_requests: int
    total_contacts_granted: int


@dataclass(slots=True, frozen=True)
class SearchSessionSummary:
    id: UUID
    employer_id: UUID
    title: str
    status: str
    role: str
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(slots=True, frozen=True)
class NextCandidateResultView:
    candidate: CandidateProfileSummary | None
    message: str | None
    is_degraded: bool = False


@dataclass(slots=True, frozen=True)
class ContactAccessResultView:
    granted: bool
    status: str
    contacts: dict[str, str | None] | None = None
    request_id: UUID | None = None
    notification_info: dict | None = None


@dataclass(slots=True, frozen=True)
class ContactRequestDetailsView:
    id: UUID
    employer_telegram_id: int
    candidate_name: str
    candidate_id: UUID
    status: str
    granted: bool


@dataclass(slots=True, frozen=True)
class CandidatePendingContactRequestView:
    id: UUID
    employer_id: UUID
    employer_company: str
    employer_telegram_id: int
    status: str
    granted: bool
    created_at: str | None = None


@dataclass(slots=True, frozen=True)
class ContactRequestDecisionView:
    granted: bool
    status: str
    request_id: UUID


@dataclass(slots=True, frozen=True)
class FileUploadUrlView:
    file_id: UUID
    upload_url: str
    method: str
    expires_in: int
    headers: dict[str, str]


class AuthGateway(ABC):
    @abstractmethod
    async def login_via_bot(
        self,
        *,
        telegram_id: int,
        role: str,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        photo_url: str | None,
    ) -> AuthSessionView:
        raise NotImplementedError

    @abstractmethod
    async def refresh_session(
        self,
        *,
        refresh_token: str,
    ) -> AuthSessionView:
        raise NotImplementedError

    @abstractmethod
    async def logout(
        self,
        *,
        refresh_token: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def verify_access_token(
        self,
        *,
        access_token: str,
    ) -> AuthVerifiedSubject:
        raise NotImplementedError


class CandidateGateway(ABC):
    @abstractmethod
    async def get_profile_by_telegram(
        self,
        *,
        access_token: str,
        telegram_id: int,
    ) -> CandidateProfileSummary | None:
        raise NotImplementedError

    @abstractmethod
    async def create_candidate(
        self,
        *,
        access_token: str,
        display_name: str,
        headline_role: str,
        telegram_contact: str,
        idempotency_key: str | None = None,
    ) -> CandidateProfileSummary:
        raise NotImplementedError

    @abstractmethod
    async def update_candidate_profile(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        display_name: str | None | _UnsetType = UNSET,
        headline_role: str | None | _UnsetType = UNSET,
        location: str | None | _UnsetType = UNSET,
        work_modes: list[str] | None | _UnsetType = UNSET,
        about_me: str | None | _UnsetType = UNSET,
        contacts_visibility: str | None | _UnsetType = UNSET,
        contacts: dict[str, str | None] | None | _UnsetType = UNSET,
        status: str | None | _UnsetType = UNSET,
        salary_min: int | None | _UnsetType = UNSET,
        salary_max: int | None | _UnsetType = UNSET,
        currency: str | None | _UnsetType = UNSET,
        english_level: str | None | _UnsetType = UNSET,
        skills: list[dict] | None | _UnsetType = UNSET,
        education: list[dict] | None | _UnsetType = UNSET,
        experiences: list[dict] | None | _UnsetType = UNSET,
        projects: list[dict] | None | _UnsetType = UNSET,
        idempotency_key: str | None = None,
    ) -> CandidateProfileSummary:
        raise NotImplementedError

    @abstractmethod
    async def get_statistics(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
    ) -> CandidateStatisticsView:
        raise NotImplementedError

    @abstractmethod
    async def get_avatar_upload_url(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        filename: str,
        content_type: str,
        idempotency_key: str | None = None,
    ) -> FileUploadUrlView:
        raise NotImplementedError

    @abstractmethod
    async def replace_avatar(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        file_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_avatar(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_resume_upload_url(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        filename: str,
        content_type: str,
        idempotency_key: str | None = None,
    ) -> FileUploadUrlView:
        raise NotImplementedError

    @abstractmethod
    async def replace_resume(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        file_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_resume(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        raise NotImplementedError


class EmployerGateway(ABC):
    @abstractmethod
    async def get_by_telegram(
        self,
        *,
        access_token: str,
        telegram_id: int,
    ) -> EmployerProfileSummary | None:
        raise NotImplementedError

    @abstractmethod
    async def create_employer(
        self,
        *,
        access_token: str,
        telegram_id: int,
        company: str | None,
        idempotency_key: str | None = None,
    ) -> EmployerProfileSummary:
        raise NotImplementedError

    @abstractmethod
    async def update_employer(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        company: str | None | _UnsetType = UNSET,
        contacts: dict[str, str | None] | None | _UnsetType = UNSET,
        idempotency_key: str | None = None,
    ) -> EmployerProfileSummary:
        raise NotImplementedError

    @abstractmethod
    async def get_statistics(
        self,
        *,
        access_token: str,
        employer_id: UUID,
    ) -> EmployerStatisticsView:
        raise NotImplementedError

    @abstractmethod
    async def create_search_session(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        title: str,
        filters: dict[str, object],
        idempotency_key: str | None = None,
    ) -> SearchSessionSummary:
        raise NotImplementedError

    @abstractmethod
    async def list_searches(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        limit: int = 10,
    ) -> list[SearchSessionSummary]:
        raise NotImplementedError

    @abstractmethod
    async def pause_search_session(
        self,
        *,
        access_token: str,
        session_id: UUID,
        idempotency_key: str | None = None,
    ) -> SearchSessionSummary:
        raise NotImplementedError

    @abstractmethod
    async def resume_search_session(
        self,
        *,
        access_token: str,
        session_id: UUID,
        idempotency_key: str | None = None,
    ) -> SearchSessionSummary:
        raise NotImplementedError

    @abstractmethod
    async def close_search_session(
        self,
        *,
        access_token: str,
        session_id: UUID,
        idempotency_key: str | None = None,
    ) -> SearchSessionSummary:
        raise NotImplementedError

    @abstractmethod
    async def get_next_candidate(
        self,
        *,
        access_token: str,
        session_id: UUID,
    ) -> NextCandidateResultView:
        raise NotImplementedError

    @abstractmethod
    async def submit_decision(
        self,
        *,
        access_token: str,
        session_id: UUID,
        candidate_id: UUID,
        decision: str,
        note: str | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_favorites(
        self,
        *,
        access_token: str,
        employer_id: UUID,
    ) -> list[CandidateProfileSummary]:
        raise NotImplementedError

    @abstractmethod
    async def get_unlocked_contacts(
        self,
        *,
        access_token: str,
        employer_id: UUID,
    ) -> list[CandidateProfileSummary]:
        raise NotImplementedError

    @abstractmethod
    async def request_contact_access(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        candidate_id: UUID,
        idempotency_key: str | None = None,
    ) -> ContactAccessResultView:
        raise NotImplementedError

    @abstractmethod
    async def get_avatar_upload_url(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        filename: str,
        content_type: str,
        idempotency_key: str | None = None,
    ) -> FileUploadUrlView:
        raise NotImplementedError

    @abstractmethod
    async def replace_avatar(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        file_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_avatar(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_document_upload_url(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        filename: str,
        content_type: str,
        idempotency_key: str | None = None,
    ) -> FileUploadUrlView:
        raise NotImplementedError

    @abstractmethod
    async def replace_document(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        file_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_document(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_contact_request_details_for_candidate(
        self,
        *,
        access_token: str,
        request_id: UUID,
    ) -> ContactRequestDetailsView:
        raise NotImplementedError

    @abstractmethod
    async def list_candidate_pending_contact_requests(
        self,
        *,
        access_token: str,
        limit: int = 10,
    ) -> list[CandidatePendingContactRequestView]:
        raise NotImplementedError

    @abstractmethod
    async def respond_contact_request(
        self,
        *,
        access_token: str,
        request_id: UUID,
        granted: bool,
        idempotency_key: str | None = None,
    ) -> ContactRequestDecisionView:
        raise NotImplementedError
