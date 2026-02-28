from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict

class SearchFilters(BaseModel):
    role: str = Field(..., description="Target job role")
    must_skills: List[str] = Field(default_factory=list)
    nice_skills: Optional[List[str]] = Field(default_factory=list)
    experience_min: Optional[float] = Field(0, ge=0)
    experience_max: Optional[float] = Field(None, ge=0)
    location: Optional[str] = None
    work_modes: Optional[List[str]] = Field(default_factory=list)
    exclude_ids: List[UUID] = Field(default_factory=list)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: Optional[str] = "RUB"
    english_level: Optional[str] = None
    about_me: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator('must_skills', 'nice_skills', mode='before')
    @classmethod
    def normalize_skills(cls, v: Any) -> List[str]:
        if not v: return []
        if isinstance(v, str): return [s.strip().lower() for s in v.split(",") if s.strip()]
        return [skill.strip().lower() for skill in v if isinstance(skill, str) and skill.strip()]

class NextCandidateRequest(BaseModel):
    session_id: UUID
    filters: SearchFilters
    session_exclude_ids: List[UUID] = Field(default_factory=list)

class CandidatePreview(BaseModel):
    id: UUID
    display_name: str
    headline_role: str
    experience_years: float
    location: Optional[str]
    skills: List[str]
    match_score: float = 0.0
    explanation: Optional[Dict[str, float]] = None
    english_level: Optional[str] = None
    about_me: Optional[str] = None

class NextCandidateResponse(BaseModel):
    candidate: Optional[CandidatePreview]