from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any, List, Union
from uuid import UUID

from app.models.employer import DecisionType, SearchStatus

class EmployerBase(BaseModel):
    company: Optional[str] = None
    contacts: Optional[dict] = None

class EmployerCreate(EmployerBase):
    telegram_id: int

class EmployerUpdate(BaseModel):
    """Модель для обновления профиля работодателя."""
    company: Optional[str] = None
    contacts: Optional[dict] = None

class Employer(EmployerBase):
    id: UUID
    telegram_id: int

    model_config = ConfigDict(from_attributes=True)

class SearchFilters(BaseModel):
    role: str = Field(..., description="Target job role")
    must_skills: List[str] = Field(default_factory=list, description="Required hard skills")
    nice_skills: Optional[List[str]] = Field(default_factory=list)
    experience_min: Optional[float] = Field(0, ge=0)
    experience_max: Optional[float] = Field(None, ge=0)
    location: Optional[str] = None
    work_modes: Optional[List[str]] = Field(default_factory=list)
    exclude_ids: List[UUID] = Field(default_factory=list)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: Optional[str] = "RUB"

    @field_validator('must_skills', 'nice_skills', 'work_modes', 'exclude_ids', mode='before')
    @classmethod
    def none_to_list(cls, v):
        return v if v is not None else []

class SearchSessionBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    filters: SearchFilters

class SearchSessionCreate(SearchSessionBase):
    pass

class SearchSession(SearchSessionBase):
    id: UUID
    employer_id: UUID
    status: SearchStatus
    filters: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)

class DecisionBase(BaseModel):
    candidate_id: UUID
    decision: DecisionType
    note: Optional[str] = None

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
    location: Optional[str] = None
    skills: List[Union[str, Dict[str, Any]]] = Field(default_factory=list)
    education: Optional[List[Any]] = Field(default_factory=list)
    projects: Optional[List[Any]] = Field(default_factory=list)
    experiences: Optional[List[Any]] = Field(default_factory=list)
    work_modes: Optional[List[str]] = Field(default_factory=list)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: Optional[str] = "RUB"
    status: Optional[str] = "active"
    contacts_visibility: Optional[str] = "on_request"
    contacts: Optional[Dict] = None
    avatars: Optional[List[Any]] = Field(default_factory=list)
    resumes: Optional[List[Any]] = Field(default_factory=list)
    english_level: Optional[str] = None
    about_me: Optional[str] = None

    match_score: float = 0.0
    explanation: Optional[Dict] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator('skills', mode='before')
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
    candidate: Optional[CandidatePreview] = None
    message: Optional[str] = None

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
    contacts: Optional[Dict[str, Any]] = None
    notification_info: Optional[Dict[str, Any]] = None