from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    computed_field,
    field_serializer,
    field_validator,
)

from app.models.candidate import ContactsVisibility, EnglishLevel, SkillKind, Status


class AvatarBase(BaseModel):
    file_id: UUID


class AvatarCreate(AvatarBase):
    pass


class Avatar(AvatarBase):
    id: UUID
    candidate_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EducationItem(BaseModel):
    level: str = Field(..., max_length=100)
    institution: str = Field(..., max_length=255)
    year: int = Field(..., ge=1950, le=2100)

    model_config = ConfigDict(from_attributes=True)


class ExperienceBase(BaseModel):
    company: str = Field(..., max_length=255)
    position: str = Field(..., max_length=255)
    start_date: date
    end_date: date | None = None
    responsibilities: str | None = None


class ExperienceCreate(ExperienceBase):
    pass


class Experience(ExperienceBase):
    id: UUID
    candidate_id: UUID

    model_config = ConfigDict(from_attributes=True)


class ProjectBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    links: HttpUrl | None = Field(None, max_length=255)

    @field_serializer("links")
    def serialize_links(self, v):
        return str(v) if v is not None else None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    links: HttpUrl | None = Field(None, max_length=255)


class Project(ProjectBase):
    id: UUID
    candidate_id: UUID

    model_config = ConfigDict(from_attributes=True)


class ResumeUploadResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int


class ResumeBase(BaseModel):
    file_id: UUID


class ResumeCreate(ResumeBase):
    pass


class Resume(ResumeBase):
    id: UUID
    candidate_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateSkillBase(BaseModel):
    skill: str = Field(..., min_length=1, max_length=100)
    kind: SkillKind
    level: int | None = Field(None, ge=1, le=5)

    @field_validator("skill")
    @classmethod
    def normalize_skill(cls, v: str) -> str:
        return v.strip().lower()


class CandidateSkillCreate(CandidateSkillBase):
    pass


class CandidateSkill(CandidateSkillBase):
    id: UUID
    candidate_id: UUID

    model_config = ConfigDict(from_attributes=True)


class CandidateStatusUpdate(BaseModel):
    status: Status


class CandidateBase(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    headline_role: str = Field(..., min_length=1, max_length=255)
    location: str | None = Field(None, max_length=255)
    work_modes: list[str] = Field(default_factory=lambda: ["remote"])
    education: list[EducationItem] = Field(default_factory=list)
    contacts_visibility: ContactsVisibility = Field(default=ContactsVisibility.ON_REQUEST)
    contacts: dict[str, str | None] | None = Field(...)
    status: Status = Field(default=Status.ACTIVE)
    salary_min: int | None = Field(None, ge=0)
    salary_max: int | None = Field(None, ge=0)
    currency: str | None = Field("RUB", max_length=10)
    english_level: EnglishLevel | None = None
    about_me: str | None = Field(None, max_length=1000)


class CandidateCreate(CandidateBase):
    telegram_id: int
    skills: list[CandidateSkillCreate] = Field(default_factory=list)
    projects: list[ProjectCreate] = Field(default_factory=list)
    experiences: list[ExperienceCreate] = Field(default_factory=list)


class CandidateUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    headline_role: str | None = Field(None, min_length=1, max_length=255)
    location: str | None = Field(None, max_length=255)
    work_modes: list[str] | None = None
    education: list[EducationItem] | None = None
    contacts_visibility: ContactsVisibility | None = None
    contacts: dict[str, str | None] | None = None
    status: Status | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    english_level: EnglishLevel | None = None
    about_me: str | None = None

    skills: list[CandidateSkillCreate] | None = None
    projects: list[ProjectCreate] | None = None
    experiences: list[ExperienceCreate] | None = None

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class Candidate(CandidateBase):
    id: UUID
    telegram_id: int
    created_at: datetime
    updated_at: datetime

    skills: list[CandidateSkill] = Field(default_factory=list)
    resumes: list[Resume] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    avatars: list[Avatar] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def experience_years(self) -> float:
        """
        Вычисляется динамически. Округляется до 1 знака.
        """
        if not self.experiences:
            return 0.0

        intervals = []
        today = date.today()

        for exp in self.experiences:
            start = exp.start_date
            end = exp.end_date if exp.end_date else today
            if start <= end:
                intervals.append([start, end])

        if not intervals:
            return 0.0

        intervals.sort(key=lambda x: x[0])

        merged = []
        for start, end in intervals:
            if not merged:
                merged.append([start, end])
            else:
                last_end = merged[-1][1]
                if start <= last_end:
                    merged[-1][1] = max(last_end, end)
                else:
                    merged.append([start, end])

        total_days = sum((end - start).days for start, end in merged)
        years = total_days / 365.25

        dec_years = Decimal(years).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        return float(dec_years)


class CandidatesBulkRequest(BaseModel):
    candidate_ids: list[UUID]


class CandidatesBulkResponse(BaseModel):
    candidates: list[Candidate]


class PaginatedCandidatesResponse(BaseModel):
    total: int
    limit: int
    offset: int
    data: list[Candidate]


class CandidateStatistics(BaseModel):
    total_views: int
    total_likes: int
    total_contact_requests: int
