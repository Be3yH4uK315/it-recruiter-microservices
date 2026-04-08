from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.application.common.contracts import CandidateShortProfile, UploadUrlResult
from app.application.employers.commands.create_employer import CreateEmployerCommand
from app.application.employers.commands.create_search_session import (
    CreateSearchSessionCommand,
    SkillInput,
)
from app.application.employers.commands.get_next_candidate import NextCandidateResult
from app.application.employers.commands.request_contact_access import (
    RequestContactAccessCommand,
    RequestContactAccessResult,
)
from app.application.employers.commands.respond_contact_request import (
    RespondContactRequestCommand,
)
from app.application.employers.commands.submit_decision import SubmitDecisionCommand
from app.application.employers.commands.update_employer import (
    UNSET_VALUE,
    UpdateEmployerCommand,
)
from app.application.employers.dto.views import (
    ContactRequestStatusView,
    EmployerView,
    map_contact_request_status_to_view,
)
from app.application.employers.queries.get_contact_request_details import ContactRequestDetails
from app.application.employers.queries.get_contact_request_status import ContactRequestStatusResult
from app.application.employers.queries.get_employer_contact_request_details import (
    EmployerContactRequestDetails,
)
from app.application.employers.queries.list_candidate_pending_contact_requests import (
    CandidatePendingContactRequest,
)
from app.domain.employer.entities import (
    ContactRequest,
    EmployerProfile,
    SearchDecision,
    SearchSession,
)
from app.domain.employer.enums import DecisionType, SearchStatus, WorkMode


class ReplaceFileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: UUID


class UploadUrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    content_type: str

    @field_validator("filename", "content_type")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized


class UploadUrlResponse(BaseModel):
    file_id: UUID
    upload_url: str
    method: str
    expires_in: int
    headers: dict[str, str]

    @classmethod
    def from_result(cls, result: UploadUrlResult) -> "UploadUrlResponse":
        return cls(
            file_id=result.file_id,
            upload_url=result.upload_url,
            method=result.method,
            expires_in=result.expires_in,
            headers=result.headers,
        )


class EmployerContactsSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = None
    telegram: str | None = None
    phone: str | None = None
    website: str | None = None

    @field_validator("email", "telegram", "phone", "website")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def to_dict(self) -> dict[str, str | None]:
        return self.model_dump()


class EmployerBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str | None = None
    contacts: EmployerContactsSchema | None = None

    @field_validator("company")
    @classmethod
    def normalize_company(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class EmployerCreateRequest(EmployerBase):
    telegram_id: int = Field(..., gt=0)

    def to_command(self) -> CreateEmployerCommand:
        return CreateEmployerCommand(
            telegram_id=self.telegram_id,
            company=self.company,
            contacts=self.contacts.to_dict() if self.contacts else None,
        )


class EmployerUpdateRequest(EmployerBase):
    def to_command(self, *, employer_id: UUID) -> UpdateEmployerCommand:
        values = self.model_dump(exclude_unset=True)

        return UpdateEmployerCommand(
            employer_id=employer_id,
            company=values.get("company", UNSET_VALUE),
            contacts=(
                self.contacts.to_dict()
                if "contacts" in values and self.contacts is not None
                else (None if "contacts" in values else UNSET_VALUE)
            ),
        )


class EmployerResponse(EmployerBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    telegram_id: int
    avatar_file_id: UUID | None = None
    avatar_download_url: str | None = None
    document_file_id: UUID | None = None
    document_download_url: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, employer: EmployerProfile) -> "EmployerResponse":
        return cls(
            id=employer.id,
            telegram_id=employer.telegram_id,
            company=employer.company,
            contacts=(
                EmployerContactsSchema(**employer.contacts.to_dict())
                if employer.contacts is not None
                else None
            ),
            avatar_file_id=employer.avatar_file_id,
            avatar_download_url=None,
            document_file_id=employer.document_file_id,
            document_download_url=None,
            created_at=employer.created_at,
            updated_at=employer.updated_at,
        )

    @classmethod
    def from_view(cls, employer: EmployerView) -> "EmployerResponse":
        return cls(
            id=employer.id,
            telegram_id=employer.telegram_id,
            company=employer.company,
            contacts=EmployerContactsSchema(**employer.contacts) if employer.contacts else None,
            avatar_file_id=employer.avatar_file_id,
            avatar_download_url=employer.avatar_download_url,
            document_file_id=employer.document_file_id,
            document_download_url=employer.document_download_url,
            created_at=employer.created_at,
            updated_at=employer.updated_at,
        )


class SearchSkillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str = Field(..., min_length=1)
    level: int | None = Field(default=None, ge=1, le=5)

    @field_validator("skill")
    @classmethod
    def normalize_skill(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("skill must not be empty")
        return normalized

    def to_input(self) -> SkillInput:
        return SkillInput(skill=self.skill, level=self.level)


class SearchFiltersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(..., min_length=2)
    must_skills: list[SearchSkillRequest] = Field(default_factory=list)
    nice_skills: list[SearchSkillRequest] = Field(default_factory=list)
    experience_min: float | None = Field(default=None, ge=0)
    experience_max: float | None = Field(default=None, ge=0)
    location: str | None = None
    work_modes: list[WorkMode] = Field(default_factory=list)
    exclude_ids: list[UUID] = Field(default_factory=list)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    currency: str | None = "RUB"
    english_level: str | None = None
    about_me: str | None = None

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("role must contain at least 2 characters")
        return normalized

    @field_validator("location", "currency", "english_level", "about_me")
    @classmethod
    def normalize_optional_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("experience_max")
    @classmethod
    def validate_experience_max(cls, value: float | None, info):
        min_value = info.data.get("experience_min")
        if value is not None and min_value is not None and value < min_value:
            raise ValueError("experience_max must be >= experience_min")
        return value

    @field_validator("salary_max")
    @classmethod
    def validate_salary_max(cls, value: int | None, info):
        min_value = info.data.get("salary_min")
        if value is not None and min_value is not None and value < min_value:
            raise ValueError("salary_max must be >= salary_min")
        return value


class SearchFiltersResponse(BaseModel):
    role: str
    must_skills: list[dict[str, Any]]
    nice_skills: list[dict[str, Any]]
    experience_min: float | None
    experience_max: float | None
    location: str | None
    work_modes: list[str]
    exclude_ids: list[str]
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    english_level: str | None
    about_me: str | None


class SearchSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=255)
    filters: SearchFiltersRequest

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("title must contain at least 3 characters")
        return normalized

    def to_command(self, *, employer_id: UUID) -> CreateSearchSessionCommand:
        return CreateSearchSessionCommand(
            employer_id=employer_id,
            title=self.title,
            role=self.filters.role,
            must_skills=[item.to_input() for item in self.filters.must_skills],
            nice_skills=[item.to_input() for item in self.filters.nice_skills],
            experience_min=self.filters.experience_min,
            experience_max=self.filters.experience_max,
            location=self.filters.location,
            work_modes=self.filters.work_modes,
            exclude_ids=self.filters.exclude_ids,
            salary_min=self.filters.salary_min,
            salary_max=self.filters.salary_max,
            currency=self.filters.currency,
            english_level=self.filters.english_level,
            about_me=self.filters.about_me,
        )


class SearchSessionResponse(BaseModel):
    id: UUID
    employer_id: UUID
    title: str
    filters: SearchFiltersResponse
    status: SearchStatus
    created_at: datetime
    updated_at: datetime
    search_offset: int = 0
    search_total: int = 0
    candidate_pool_size: int = 0

    @classmethod
    def from_domain(cls, session: SearchSession) -> "SearchSessionResponse":
        raw = session.filters.to_primitives()
        return cls(
            id=session.id,
            employer_id=session.employer_id,
            title=session.title,
            filters=SearchFiltersResponse(
                role=raw["role"],
                must_skills=raw["must_skills"],
                nice_skills=raw["nice_skills"],
                experience_min=raw["experience_min"],
                experience_max=raw["experience_max"],
                location=raw["location"],
                work_modes=raw["work_modes"],
                exclude_ids=raw["exclude_ids"],
                salary_min=raw["salary_min"],
                salary_max=raw["salary_max"],
                currency=raw["currency"],
                english_level=raw["english_level"],
                about_me=raw.get("about_me"),
            ),
            status=session.status,
            created_at=session.created_at,
            updated_at=session.updated_at,
            search_offset=session.search_offset,
            search_total=session.search_total,
            candidate_pool_size=len(session.candidate_pool),
        )


class DecisionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    decision: DecisionType
    note: str | None = None

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def to_command(self, *, session_id: UUID) -> SubmitDecisionCommand:
        return SubmitDecisionCommand(
            session_id=session_id,
            candidate_id=self.candidate_id,
            decision=self.decision,
            note=self.note,
        )


class DecisionResponse(BaseModel):
    candidate_id: UUID
    decision: DecisionType
    note: str | None = None
    created_at: datetime

    @classmethod
    def from_domain(cls, decision: SearchDecision) -> "DecisionResponse":
        return cls(
            candidate_id=decision.candidate_id,
            decision=decision.decision,
            note=decision.note,
            created_at=decision.created_at,
        )


class CandidateSkillResponse(BaseModel):
    skill: str
    kind: str
    level: int | None = None


class CandidateEducationResponse(BaseModel):
    level: str
    institution: str
    year: int


class CandidateExperienceResponse(BaseModel):
    company: str
    position: str
    start_date: str
    end_date: str | None = None
    responsibilities: str | None = None


class CandidateProjectResponse(BaseModel):
    title: str
    description: str | None = None
    links: list[str] = Field(default_factory=list)


class CandidatePreviewResponse(BaseModel):
    id: UUID
    display_name: str
    headline_role: str
    location: str | None
    work_modes: list[str]
    experience_years: float

    contacts_visibility: str | None
    contacts: dict[str, str | None] | None
    can_view_contacts: bool

    status: str | None
    english_level: str | None
    about_me: str | None

    salary_min: int | None
    salary_max: int | None
    currency: str | None

    skills: list[CandidateSkillResponse]
    education: list[CandidateEducationResponse]
    experiences: list[CandidateExperienceResponse]
    projects: list[CandidateProjectResponse]

    avatar_file_id: UUID | None = None
    avatar_download_url: str | None = None
    resume_file_id: UUID | None = None
    resume_download_url: str | None = None

    created_at: str | None = None
    updated_at: str | None = None
    version_id: int | None = None

    explanation: dict[str, Any] | None = None
    match_score: float = 0.0

    @classmethod
    def from_contract(cls, profile: CandidateShortProfile) -> "CandidatePreviewResponse":
        return cls(
            id=profile.id,
            display_name=profile.display_name,
            headline_role=profile.headline_role,
            location=profile.location,
            work_modes=profile.work_modes,
            experience_years=profile.experience_years,
            contacts_visibility=profile.contacts_visibility,
            contacts=profile.contacts,
            can_view_contacts=profile.can_view_contacts,
            status=profile.status,
            english_level=profile.english_level,
            about_me=profile.about_me,
            salary_min=profile.salary_min,
            salary_max=profile.salary_max,
            currency=profile.currency,
            skills=[
                CandidateSkillResponse(
                    skill=str(item["skill"]),
                    kind=str(item["kind"]),
                    level=item.get("level"),
                )
                for item in profile.skills
                if isinstance(item, dict) and "skill" in item and "kind" in item
            ],
            education=[
                CandidateEducationResponse(
                    level=str(item["level"]),
                    institution=str(item["institution"]),
                    year=int(item["year"]),
                )
                for item in profile.education
                if isinstance(item, dict)
                and "level" in item
                and "institution" in item
                and "year" in item
            ],
            experiences=[
                CandidateExperienceResponse(
                    company=str(item["company"]),
                    position=str(item["position"]),
                    start_date=str(item["start_date"]),
                    end_date=str(item["end_date"]) if item.get("end_date") is not None else None,
                    responsibilities=(
                        str(item["responsibilities"])
                        if item.get("responsibilities") is not None
                        else None
                    ),
                )
                for item in profile.experiences
                if isinstance(item, dict)
                and "company" in item
                and "position" in item
                and "start_date" in item
            ],
            projects=[
                CandidateProjectResponse(
                    title=str(item["title"]),
                    description=(
                        str(item["description"]) if item.get("description") is not None else None
                    ),
                    links=[str(link) for link in item.get("links", []) if isinstance(link, str)],
                )
                for item in profile.projects
                if isinstance(item, dict) and "title" in item
            ],
            avatar_file_id=profile.avatar_file_id,
            avatar_download_url=profile.avatar_download_url,
            resume_file_id=profile.resume_file_id,
            resume_download_url=profile.resume_download_url,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            version_id=profile.version_id,
            explanation=profile.explanation,
            match_score=profile.match_score,
        )


class NextCandidateResponse(BaseModel):
    candidate: CandidatePreviewResponse | None = None
    message: str | None = None

    @classmethod
    def from_result(cls, result: NextCandidateResult) -> "NextCandidateResponse":
        return cls(
            candidate=(
                CandidatePreviewResponse.from_contract(result.candidate)
                if result.candidate
                else None
            ),
            message=result.message,
        )


class ContactAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID

    def to_command(self, *, employer_id: UUID) -> RequestContactAccessCommand:
        return RequestContactAccessCommand(
            employer_id=employer_id,
            candidate_id=self.candidate_id,
        )


class ContactAccessResponse(BaseModel):
    granted: bool
    status: ContactRequestStatusView
    contacts: dict | None = None
    notification_info: dict | None = None
    request_id: UUID | None = None

    @classmethod
    def from_result(cls, result: RequestContactAccessResult) -> "ContactAccessResponse":
        return cls(
            granted=result.granted,
            status=result.status,
            contacts=result.contacts,
            notification_info=result.notification_info,
            request_id=result.request_id,
        )


class ContactRequestResponse(BaseModel):
    id: UUID
    employer_id: UUID
    candidate_id: UUID
    status: ContactRequestStatusView
    granted: bool
    created_at: datetime
    responded_at: datetime | None = None

    @classmethod
    def from_domain(cls, request: ContactRequest) -> "ContactRequestResponse":
        return cls(
            id=request.id,
            employer_id=request.employer_id,
            candidate_id=request.candidate_id,
            status=map_contact_request_status_to_view(request.status),
            granted=request.granted,
            created_at=request.created_at,
            responded_at=request.responded_at,
        )


class ContactRequestDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    granted: bool

    def to_command(
        self,
        *,
        request_id: UUID,
        candidate_id: UUID,
    ) -> RespondContactRequestCommand:
        return RespondContactRequestCommand(
            request_id=request_id,
            candidate_id=candidate_id,
            granted=self.granted,
        )


class ContactRequestDecisionResponse(BaseModel):
    granted: bool
    status: ContactRequestStatusView
    request_id: UUID

    @classmethod
    def from_domain(cls, request: ContactRequest) -> "ContactRequestDecisionResponse":
        return cls(
            granted=request.granted,
            status=map_contact_request_status_to_view(request.status),
            request_id=request.id,
        )


class EmployerContactRequestDetailsResponse(BaseModel):
    id: UUID
    employer_id: UUID
    candidate_id: UUID
    candidate_name: str
    status: ContactRequestStatusView
    granted: bool
    created_at: datetime
    responded_at: datetime | None = None

    @classmethod
    def from_result(
        cls,
        result: EmployerContactRequestDetails,
    ) -> "EmployerContactRequestDetailsResponse":
        return cls(
            id=result.id,
            employer_id=result.employer_id,
            candidate_id=result.candidate_id,
            candidate_name=result.candidate_name,
            status=result.status,
            granted=result.granted,
            created_at=datetime.fromisoformat(result.created_at.replace("Z", "+00:00")),
            responded_at=(
                datetime.fromisoformat(result.responded_at.replace("Z", "+00:00"))
                if result.responded_at
                else None
            ),
        )


class ContactRequestDetailsResponse(BaseModel):
    id: UUID
    employer_telegram_id: int
    candidate_name: str
    candidate_id: UUID
    status: ContactRequestStatusView
    granted: bool

    @classmethod
    def from_result(cls, result: ContactRequestDetails) -> "ContactRequestDetailsResponse":
        return cls(
            id=result.id,
            employer_telegram_id=result.employer_telegram_id,
            candidate_name=result.candidate_name,
            candidate_id=result.candidate_id,
            status=result.status,
            granted=result.granted,
        )


class CandidatePendingContactRequestResponse(BaseModel):
    id: UUID
    employer_id: UUID
    employer_company: str
    employer_telegram_id: int
    status: ContactRequestStatusView
    granted: bool
    created_at: datetime

    @classmethod
    def from_result(
        cls,
        result: CandidatePendingContactRequest,
    ) -> "CandidatePendingContactRequestResponse":
        return cls(
            id=result.id,
            employer_id=result.employer_id,
            employer_company=result.employer_company,
            employer_telegram_id=result.employer_telegram_id,
            status=ContactRequestStatusView(result.status),
            granted=result.granted,
            created_at=result.created_at,
        )


class ContactRequestStatusResponse(BaseModel):
    exists: bool
    status: ContactRequestStatusView
    granted: bool
    request_id: UUID | None = None

    @classmethod
    def from_result(cls, result: ContactRequestStatusResult) -> "ContactRequestStatusResponse":
        return cls(
            exists=result.exists,
            status=result.status,
            granted=result.granted,
            request_id=result.request_id,
        )


class EmployerStatisticsResponse(BaseModel):
    total_viewed: int
    total_liked: int
    total_contact_requests: int
    total_contacts_granted: int


class CandidateStatisticsResponse(BaseModel):
    total_views: int
    total_likes: int
    total_contact_requests: int
