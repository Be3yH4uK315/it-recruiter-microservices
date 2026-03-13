from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.employer import DecisionType, SearchStatus


class EmployerBase(BaseModel):
    company: str | None = None
    contacts: dict | None = None


class EmployerCreate(EmployerBase):
    telegram_id: int


class EmployerUpdate(BaseModel):
    company: str | None = None
    contacts: dict | None = None


class Employer(EmployerBase):
    id: UUID
    telegram_id: int

    model_config = ConfigDict(from_attributes=True)


class SearchFilters(BaseModel):
    role: str = Field(..., description="Target job role")
    must_skills: list[dict[str, Any]] = Field(default_factory=list)
    nice_skills: list[dict[str, Any]] | None = Field(default_factory=list)
    experience_min: float | None = Field(0, ge=0)
    experience_max: float | None = Field(None, ge=0)
    location: str | None = None
    work_modes: list[str] | None = Field(default_factory=list)
    exclude_ids: list[UUID] = Field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = "RUB"
    english_level: str | None = None

    @field_validator("work_modes", "exclude_ids", mode="before")
    @classmethod
    def none_to_list(cls, v):
        return v if v is not None else []

    @field_validator("must_skills", "nice_skills", mode="before")
    @classmethod
    def normalize_skills(cls, v: Any) -> list[dict[str, Any]]:
        if not v:
            return []

        normalized = []
        if isinstance(v, str):
            return [{"skill": s.strip().lower(), "level": 3} for s in v.split(",") if s.strip()]

        for item in v:
            if isinstance(item, str):
                normalized.append({"skill": item.strip().lower(), "level": 3})
            elif isinstance(item, dict) and "skill" in item:
                item["skill"] = item["skill"].strip().lower()
                if "level" not in item:
                    item["level"] = 3
                normalized.append(item)
        return normalized


class SearchSessionBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    filters: SearchFilters


class SearchSessionCreate(SearchSessionBase):
    pass


class SearchSession(SearchSessionBase):
    id: UUID
    employer_id: UUID
    status: SearchStatus
    filters: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class DecisionBase(BaseModel):
    candidate_id: UUID
    decision: DecisionType
    note: str | None = None


class DecisionCreate(DecisionBase):
    pass


class Decision(DecisionBase):
    id: UUID
    session_id: UUID

    model_config = ConfigDict(from_attributes=True)


class CandidatePreview(BaseModel):
    id: UUID
    display_name: str
    headline_role: str
    experience_years: float
    location: str | None = None
    skills: list[str | dict[str, Any]] = Field(default_factory=list)
    education: list[Any] | None = Field(default_factory=list)
    projects: list[Any] | None = Field(default_factory=list)
    experiences: list[Any] | None = Field(default_factory=list)
    work_modes: list[str] | None = Field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = "RUB"
    status: str | None = "active"
    contacts_visibility: str | None = "on_request"
    contacts: dict | None = None
    avatars: list[Any] | None = Field(default_factory=list)
    resumes: list[Any] | None = Field(default_factory=list)
    english_level: str | None = None
    about_me: str | None = None

    match_score: float = 0.0
    explanation: dict | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, v):
        normalized = []
        if not v:
            return []
        for item in v:
            if isinstance(item, str):
                normalized.append(item)
            elif isinstance(item, dict) and "skill" in item:
                skill_str = item["skill"]
                if item.get("level"):
                    skill_str += f" ({item['level']}/5)"
                normalized.append(skill_str)
        return normalized


class NextCandidateResponse(BaseModel):
    candidate: CandidatePreview | None = None
    message: str | None = None


class ContactsRequestCreate(BaseModel):
    candidate_id: UUID


class ContactsRequest(ContactsRequestCreate):
    id: UUID
    employer_id: UUID
    granted: bool

    model_config = ConfigDict(from_attributes=True)


class ContactUpdateRequest(BaseModel):
    granted: bool


class ContactDetailsRequest(BaseModel):
    id: UUID
    employer_telegram_id: int
    candidate_name: str
    candidate_id: UUID

    model_config = ConfigDict(from_attributes=True)


class ContactDetailsResponse(BaseModel):
    granted: bool
    contacts: dict[str, Any] | None = None
    notification_info: dict[str, Any] | None = None


class EmployerStatisticsResponse(BaseModel):
    total_viewed: int
    total_liked: int
    total_contact_requests: int
    total_contacts_granted: int


class CandidateStatisticsResponse(BaseModel):
    total_views: int
    total_likes: int
    total_contact_requests: int
