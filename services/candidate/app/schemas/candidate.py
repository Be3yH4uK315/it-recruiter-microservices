from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.application.candidates.commands.create_candidate import (
    CreateCandidateCommand,
)
from app.application.candidates.commands.create_candidate import (
    EducationInput as CreateEducationInput,
)
from app.application.candidates.commands.create_candidate import (
    ExperienceInput as CreateExperienceInput,
)
from app.application.candidates.commands.create_candidate import ProjectInput as CreateProjectInput
from app.application.candidates.commands.create_candidate import SkillInput as CreateSkillInput
from app.application.candidates.commands.update_candidate import (
    UNSET_VALUE,
    UpdateCandidateCommand,
)
from app.application.candidates.commands.update_candidate import (
    EducationInput as UpdateEducationInput,
)
from app.application.candidates.commands.update_candidate import (
    ExperienceInput as UpdateExperienceInput,
)
from app.application.candidates.commands.update_candidate import ProjectInput as UpdateProjectInput
from app.application.candidates.commands.update_candidate import SkillInput as UpdateSkillInput
from app.application.candidates.dto.views import CandidateEmployerView, CandidateProfileView
from app.application.candidates.queries.get_candidate_search_document import (
    CandidateSearchDocumentView,
)
from app.application.candidates.queries.get_candidate_statistics import (
    CandidateStatisticsResult,
)
from app.application.common.contracts import UploadUrlResult
from app.domain.candidate.entities import CandidateProfile
from app.domain.candidate.enums import (
    CandidateStatus,
    ContactsVisibility,
    EnglishLevel,
    SkillKind,
    WorkMode,
)

_ALLOWED_CONTACT_KEYS = {"telegram", "email", "phone"}


class SkillPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str
    kind: SkillKind
    level: int | None = Field(default=None, ge=1, le=5)

    @field_validator("skill")
    @classmethod
    def validate_skill(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("skill must not be empty")
        return normalized


class EducationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str
    institution: str
    year: int = Field(..., ge=1950, le=2100)

    @field_validator("level", "institution")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized


class ExperiencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str
    position: str
    start_date: date
    end_date: date | None = None
    responsibilities: str | None = None

    @field_validator("company", "position")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("responsibilities")
    @classmethod
    def normalize_responsibilities(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ProjectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    links: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title must not be empty")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("links")
    @classmethod
    def normalize_links(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        for item in value:
            normalized = item.strip()
            if not normalized:
                continue

            parsed = urlparse(normalized)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("project links must be valid http/https urls")

            result.append(normalized)
        return result


class CreateCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    headline_role: str
    location: str | None = None
    work_modes: list[WorkMode] = Field(default_factory=lambda: [WorkMode.REMOTE])
    contacts_visibility: ContactsVisibility = ContactsVisibility.ON_REQUEST
    contacts: dict[str, str | None]
    status: CandidateStatus = CandidateStatus.ACTIVE
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    currency: str | None = "RUB"
    english_level: EnglishLevel | None = None
    about_me: str | None = None
    skills: list[SkillPayload] = Field(default_factory=list)
    education: list[EducationPayload] = Field(default_factory=list)
    experiences: list[ExperiencePayload] = Field(default_factory=list)
    projects: list[ProjectPayload] = Field(default_factory=list)

    @field_validator("display_name", "headline_role")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("location", "about_me", "currency")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("salary_max")
    @classmethod
    def validate_salary_max(cls, value: int | None, info) -> int | None:
        salary_min = info.data.get("salary_min")
        if value is not None and salary_min is not None and value < salary_min:
            raise ValueError("salary_max must be >= salary_min")
        return value

    @field_validator("contacts")
    @classmethod
    def validate_contacts(
        cls,
        value: dict[str, str | None] | None,
    ) -> dict[str, str | None] | None:
        if value is None:
            raise ValueError("contacts is required")

        result: dict[str, str | None] = {}
        for key, item in value.items():
            normalized_key = key.strip().lower()
            if normalized_key not in _ALLOWED_CONTACT_KEYS:
                raise ValueError("contacts supports only telegram, email, phone")

            if item is None:
                result[normalized_key] = None
                continue

            normalized_value = item.strip()
            result[normalized_key] = normalized_value or None

        if not result.get("telegram"):
            raise ValueError("contacts.telegram is required")

        return result

    def to_command(self, *, telegram_id: int) -> CreateCandidateCommand:
        return CreateCandidateCommand(
            telegram_id=telegram_id,
            display_name=self.display_name,
            headline_role=self.headline_role,
            location=self.location,
            work_modes=self.work_modes,
            contacts_visibility=self.contacts_visibility,
            contacts=self.contacts,
            status=self.status,
            salary_min=self.salary_min,
            salary_max=self.salary_max,
            currency=self.currency,
            english_level=self.english_level,
            about_me=self.about_me,
            skills=[
                CreateSkillInput(
                    skill=item.skill,
                    kind=item.kind,
                    level=item.level,
                )
                for item in self.skills
            ],
            education=[
                CreateEducationInput(
                    level=item.level,
                    institution=item.institution,
                    year=item.year,
                )
                for item in self.education
            ],
            experiences=[
                CreateExperienceInput(
                    company=item.company,
                    position=item.position,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    responsibilities=item.responsibilities,
                )
                for item in self.experiences
            ],
            projects=[
                CreateProjectInput(
                    title=item.title,
                    description=item.description,
                    links=tuple(item.links),
                )
                for item in self.projects
            ],
        )


class UpdateCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    headline_role: str | None = None
    location: str | None = None
    work_modes: list[WorkMode] | None = None
    contacts_visibility: ContactsVisibility | None = None
    contacts: dict[str, str | None] | None = None
    status: CandidateStatus | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    currency: str | None = None
    english_level: EnglishLevel | None = None
    about_me: str | None = None
    skills: list[SkillPayload] | None = None
    education: list[EducationPayload] | None = None
    experiences: list[ExperiencePayload] | None = None
    projects: list[ProjectPayload] | None = None

    @field_validator("display_name", "headline_role")
    @classmethod
    def validate_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("location", "about_me", "currency")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("salary_max")
    @classmethod
    def validate_salary_max(cls, value: int | None, info) -> int | None:
        salary_min = info.data.get("salary_min")
        if value is not None and salary_min is not None and value < salary_min:
            raise ValueError("salary_max must be >= salary_min")
        return value

    @field_validator("contacts")
    @classmethod
    def validate_contacts(
        cls,
        value: dict[str, str | None] | None,
    ) -> dict[str, str | None] | None:
        if value is None:
            return None

        result: dict[str, str | None] = {}
        for key, item in value.items():
            normalized_key = key.strip().lower()
            if normalized_key not in _ALLOWED_CONTACT_KEYS:
                raise ValueError("contacts supports only telegram, email, phone")

            if item is None:
                result[normalized_key] = None
                continue

            normalized_value = item.strip()
            result[normalized_key] = normalized_value or None

        if not result.get("telegram"):
            raise ValueError("contacts.telegram is required")

        return result

    def to_command(self, *, candidate_id: UUID) -> UpdateCandidateCommand:
        values = self.model_dump(exclude_unset=True)

        return UpdateCandidateCommand(
            candidate_id=candidate_id,
            display_name=values.get("display_name", UNSET_VALUE),
            headline_role=values.get("headline_role", UNSET_VALUE),
            location=values.get("location", UNSET_VALUE),
            work_modes=values.get("work_modes", UNSET_VALUE),
            contacts_visibility=values.get("contacts_visibility", UNSET_VALUE),
            contacts=values.get("contacts", UNSET_VALUE),
            status=values.get("status", UNSET_VALUE),
            salary_min=values.get("salary_min", UNSET_VALUE),
            salary_max=values.get("salary_max", UNSET_VALUE),
            currency=values.get("currency", UNSET_VALUE),
            english_level=values.get("english_level", UNSET_VALUE),
            about_me=values.get("about_me", UNSET_VALUE),
            skills=(
                [
                    UpdateSkillInput(
                        skill=item.skill,
                        kind=item.kind,
                        level=item.level,
                    )
                    for item in self.skills
                ]
                if "skills" in values
                else UNSET_VALUE
            ),
            education=(
                [
                    UpdateEducationInput(
                        level=item.level,
                        institution=item.institution,
                        year=item.year,
                    )
                    for item in self.education
                ]
                if "education" in values
                else UNSET_VALUE
            ),
            experiences=(
                [
                    UpdateExperienceInput(
                        company=item.company,
                        position=item.position,
                        start_date=item.start_date,
                        end_date=item.end_date,
                        responsibilities=item.responsibilities,
                    )
                    for item in self.experiences
                ]
                if "experiences" in values
                else UNSET_VALUE
            ),
            projects=(
                [
                    UpdateProjectInput(
                        title=item.title,
                        description=item.description,
                        links=tuple(item.links),
                    )
                    for item in self.projects
                ]
                if "projects" in values
                else UNSET_VALUE
            ),
        )


class CandidateSkillResponse(BaseModel):
    skill: str
    kind: SkillKind
    level: int | None = None


class CandidateEducationResponse(BaseModel):
    level: str
    institution: str
    year: int


class CandidateExperienceResponse(BaseModel):
    company: str
    position: str
    start_date: date
    end_date: date | None = None
    responsibilities: str | None = None


class CandidateProjectResponse(BaseModel):
    title: str
    description: str | None = None
    links: list[str] = Field(default_factory=list)


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    telegram_id: int
    display_name: str
    headline_role: str
    location: str | None
    work_modes: list[WorkMode]
    contacts_visibility: ContactsVisibility
    contacts: dict[str, str | None] | None
    status: CandidateStatus
    english_level: EnglishLevel | None
    about_me: str | None
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    skills: list[CandidateSkillResponse]
    education: list[CandidateEducationResponse]
    experiences: list[CandidateExperienceResponse]
    projects: list[CandidateProjectResponse]
    avatar_file_id: UUID | None
    resume_file_id: UUID | None
    created_at: datetime | None
    updated_at: datetime | None
    version_id: int

    @classmethod
    def from_domain(cls, candidate: CandidateProfile) -> "CandidateResponse":
        salary_range = candidate.salary_range

        return cls(
            id=candidate.id,
            telegram_id=candidate.telegram_id,
            display_name=candidate.display_name,
            headline_role=candidate.headline_role,
            location=candidate.location,
            work_modes=candidate.work_modes,
            contacts_visibility=candidate.contacts_visibility,
            contacts=candidate.contacts,
            status=candidate.status,
            english_level=candidate.english_level,
            about_me=candidate.about_me,
            salary_min=salary_range.min_amount if salary_range is not None else None,
            salary_max=salary_range.max_amount if salary_range is not None else None,
            currency=salary_range.currency if salary_range is not None else None,
            skills=[
                CandidateSkillResponse(
                    skill=item.skill,
                    kind=item.kind,
                    level=item.level,
                )
                for item in candidate.skills
            ],
            education=[
                CandidateEducationResponse(
                    level=item.level,
                    institution=item.institution,
                    year=item.year,
                )
                for item in candidate.education
            ],
            experiences=[
                CandidateExperienceResponse(
                    company=item.company,
                    position=item.position,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    responsibilities=item.responsibilities,
                )
                for item in candidate.experiences
            ],
            projects=[
                CandidateProjectResponse(
                    title=item.title,
                    description=item.description,
                    links=list(item.links),
                )
                for item in candidate.projects
            ],
            avatar_file_id=candidate.avatar.file_id if candidate.avatar is not None else None,
            resume_file_id=candidate.resume.file_id if candidate.resume is not None else None,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
            version_id=candidate.version_id,
        )


class CandidateEmployerViewResponse(BaseModel):
    id: UUID
    display_name: str
    headline_role: str
    location: str | None
    work_modes: list[WorkMode]
    experience_years: float
    contacts_visibility: ContactsVisibility
    contacts: dict[str, str | None] | None
    can_view_contacts: bool
    status: CandidateStatus
    english_level: EnglishLevel | None
    about_me: str | None
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    skills: list[CandidateSkillResponse]
    education: list[CandidateEducationResponse]
    experiences: list[CandidateExperienceResponse]
    projects: list[CandidateProjectResponse]
    avatar_file_id: UUID | None
    avatar_download_url: str | None
    resume_file_id: UUID | None
    resume_download_url: str | None
    created_at: datetime | None
    updated_at: datetime | None
    version_id: int

    @classmethod
    def from_view(cls, view: CandidateEmployerView) -> "CandidateEmployerViewResponse":
        return cls(
            id=view.id,
            display_name=view.display_name,
            headline_role=view.headline_role,
            location=view.location,
            work_modes=view.work_modes,
            experience_years=view.experience_years,
            contacts_visibility=view.contacts_visibility,
            contacts=view.contacts,
            can_view_contacts=view.can_view_contacts,
            status=view.status,
            english_level=view.english_level,
            about_me=view.about_me,
            salary_min=view.salary_min,
            salary_max=view.salary_max,
            currency=view.currency,
            skills=[
                CandidateSkillResponse(
                    skill=item.skill,
                    kind=item.kind,
                    level=item.level,
                )
                for item in view.skills
            ],
            education=[
                CandidateEducationResponse(
                    level=item.level,
                    institution=item.institution,
                    year=item.year,
                )
                for item in view.education
            ],
            experiences=[
                CandidateExperienceResponse(
                    company=item.company,
                    position=item.position,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    responsibilities=item.responsibilities,
                )
                for item in view.experiences
            ],
            projects=[
                CandidateProjectResponse(
                    title=item.title,
                    description=item.description,
                    links=item.links or [],
                )
                for item in view.projects
            ],
            avatar_file_id=view.avatar_file_id,
            avatar_download_url=view.avatar_download_url,
            resume_file_id=view.resume_file_id,
            resume_download_url=view.resume_download_url,
            created_at=view.created_at,
            updated_at=view.updated_at,
            version_id=view.version_id,
        )


class CandidateStatisticsResponse(BaseModel):
    total_views: int
    total_likes: int
    total_contact_requests: int
    is_degraded: bool = False

    @classmethod
    def from_result(cls, result: CandidateStatisticsResult) -> "CandidateStatisticsResponse":
        return cls(
            total_views=result.total_views,
            total_likes=result.total_likes,
            total_contact_requests=result.total_contact_requests,
            is_degraded=result.is_degraded,
        )


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


class CandidateBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_ids: list[UUID] = Field(default_factory=list, max_length=500)


class CandidateBatchResponse(BaseModel):
    items: list[CandidateResponse]

    @classmethod
    def from_domain_many(cls, candidates: list[CandidateProfile]) -> "CandidateBatchResponse":
        return cls(items=[CandidateResponse.from_domain(item) for item in candidates])


class CandidateInternalResolveResponse(BaseModel):
    id: UUID
    telegram_id: int
    status: CandidateStatus
    is_registered: bool = True

    @classmethod
    def from_domain(cls, candidate: CandidateProfile) -> "CandidateInternalResolveResponse":
        return cls(
            id=candidate.id,
            telegram_id=candidate.telegram_id,
            status=candidate.status,
            is_registered=True,
        )


class CandidateSearchDocumentResponse(BaseModel):
    id: UUID
    telegram_id: int
    display_name: str
    headline_role: str
    location: str | None
    work_modes: list[str]
    contacts_visibility: str
    status: str
    english_level: str | None
    about_me: str | None
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    skills: list[dict[str, Any]]
    education: list[dict[str, Any]]
    experiences: list[dict[str, Any]]
    projects: list[dict[str, Any]]
    avatar_file_id: str | None
    resume_file_id: str | None
    created_at: str | None
    updated_at: str | None
    version_id: int

    @classmethod
    def from_view(cls, view: CandidateSearchDocumentView) -> "CandidateSearchDocumentResponse":
        return cls(
            id=view.id,
            telegram_id=view.telegram_id,
            display_name=view.display_name,
            headline_role=view.headline_role,
            location=view.location,
            work_modes=view.work_modes,
            contacts_visibility=view.contacts_visibility,
            status=view.status,
            english_level=view.english_level,
            about_me=view.about_me,
            salary_min=view.salary_min,
            salary_max=view.salary_max,
            currency=view.currency,
            skills=view.skills,
            education=view.education,
            experiences=view.experiences,
            projects=view.projects,
            avatar_file_id=view.avatar_file_id,
            resume_file_id=view.resume_file_id,
            created_at=view.created_at,
            updated_at=view.updated_at,
            version_id=view.version_id,
        )


class CandidateSearchDocumentListResponse(BaseModel):
    items: list[CandidateSearchDocumentResponse]

    @classmethod
    def from_views(
        cls,
        views: list[CandidateSearchDocumentView],
    ) -> "CandidateSearchDocumentListResponse":
        return cls(
            items=[CandidateSearchDocumentResponse.from_view(item) for item in views],
        )


class CandidateProfileResponse(BaseModel):
    id: UUID
    telegram_id: int
    display_name: str
    headline_role: str
    location: str | None
    work_modes: list[WorkMode]
    experience_years: float
    contacts_visibility: ContactsVisibility
    contacts: dict[str, str | None] | None
    status: CandidateStatus
    english_level: EnglishLevel | None
    about_me: str | None
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    skills: list[CandidateSkillResponse]
    education: list[CandidateEducationResponse]
    experiences: list[CandidateExperienceResponse]
    projects: list[CandidateProjectResponse]
    avatar_file_id: UUID | None
    avatar_download_url: str | None
    resume_file_id: UUID | None
    resume_download_url: str | None
    created_at: datetime | None
    updated_at: datetime | None
    version_id: int

    @classmethod
    def from_view(cls, view: CandidateProfileView) -> "CandidateProfileResponse":
        return cls(
            id=view.id,
            telegram_id=view.telegram_id,
            display_name=view.display_name,
            headline_role=view.headline_role,
            location=view.location,
            work_modes=view.work_modes,
            experience_years=view.experience_years,
            contacts_visibility=view.contacts_visibility,
            contacts=view.contacts,
            status=view.status,
            english_level=view.english_level,
            about_me=view.about_me,
            salary_min=view.salary_min,
            salary_max=view.salary_max,
            currency=view.currency,
            skills=[
                CandidateSkillResponse(
                    skill=item.skill,
                    kind=item.kind,
                    level=item.level,
                )
                for item in view.skills
            ],
            education=[
                CandidateEducationResponse(
                    level=item.level,
                    institution=item.institution,
                    year=item.year,
                )
                for item in view.education
            ],
            experiences=[
                CandidateExperienceResponse(
                    company=item.company,
                    position=item.position,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    responsibilities=item.responsibilities,
                )
                for item in view.experiences
            ],
            projects=[
                CandidateProjectResponse(
                    title=item.title,
                    description=item.description,
                    links=item.links or [],
                )
                for item in view.projects
            ],
            avatar_file_id=view.avatar_file_id,
            avatar_download_url=view.avatar_download_url,
            resume_file_id=view.resume_file_id,
            resume_download_url=view.resume_download_url,
            created_at=view.created_at,
            updated_at=view.updated_at,
            version_id=view.version_id,
        )
