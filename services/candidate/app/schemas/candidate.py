from pydantic import BaseModel, Field, ConfigDict, HttpUrl, computed_field, field_serializer, field_validator
from typing import Optional, List, Dict
from uuid import UUID
from decimal import ROUND_HALF_UP, Decimal
from datetime import datetime, date

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
    end_date: Optional[date] = None
    responsibilities: Optional[str] = None

class ExperienceCreate(ExperienceBase):
    pass

class Experience(ExperienceBase):
    id: UUID
    candidate_id: UUID

    model_config = ConfigDict(from_attributes=True)

class ProjectBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    links: Optional[HttpUrl] = Field(None, max_length=255)

    @field_serializer("links")
    def serialize_links(self, v):
        return str(v) if v is not None else None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    links: Optional[HttpUrl] = Field(None, max_length=255)

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
    level: Optional[int] = Field(None, ge=1, le=5)

    @field_validator('skill')
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
    location: Optional[str] = Field(None, max_length=255)
    work_modes: List[str] = Field(default_factory=lambda: ["remote"])
    education: List[EducationItem] = Field(default_factory=list)
    contacts_visibility: ContactsVisibility = Field(default=ContactsVisibility.ON_REQUEST)
    contacts: Optional[Dict[str, Optional[str]]] = Field(...)
    status: Status = Field(default=Status.ACTIVE)
    salary_min: Optional[int] = Field(None, ge=0)
    salary_max: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field("RUB", max_length=10)
    english_level: Optional[EnglishLevel] = None
    about_me: Optional[str] = Field(None, max_length=1000)

class CandidateCreate(CandidateBase):
    telegram_id: int
    skills: List[CandidateSkillCreate] = Field(default_factory=list)
    projects: List[ProjectCreate] = Field(default_factory=list)
    experiences: List[ExperienceCreate] = Field(default_factory=list)

class CandidateUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    headline_role: Optional[str] = Field(None, min_length=1, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    work_modes: Optional[List[str]] = None
    education: Optional[List[EducationItem]] = None
    contacts_visibility: Optional[ContactsVisibility] = None
    contacts: Optional[Dict[str, Optional[str]]] = None
    status: Optional[Status] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: Optional[str] = None
    english_level: Optional[EnglishLevel] = None
    about_me: Optional[str] = None
    
    skills: Optional[List[CandidateSkillCreate]] = None
    projects: Optional[List[ProjectCreate]] = None
    experiences: Optional[List[ExperienceCreate]] = None

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

class Candidate(CandidateBase):
    id: UUID
    telegram_id: int
    created_at: datetime
    updated_at: datetime
    
    skills: List[CandidateSkill] = Field(default_factory=list)
    resumes: List[Resume] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    experiences: List[Experience] = Field(default_factory=list)
    avatars: List[Avatar] = Field(default_factory=list)

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
    candidate_ids: List[UUID]

class CandidatesBulkResponse(BaseModel):
    candidates: List[Candidate]

class PaginatedCandidatesResponse(BaseModel):
    total: int
    limit: int
    offset: int
    data: List[Candidate]
