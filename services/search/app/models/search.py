from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchFilters(BaseModel):
    role: str = Field(..., description="Target job role")
    must_skills: list[str | dict[str, Any]] = Field(default_factory=list)
    nice_skills: list[str | dict[str, Any]] | None = Field(default_factory=list)
    experience_min: float | None = Field(0, ge=0)
    experience_max: float | None = Field(None, ge=0)
    location: str | None = None
    work_modes: list[str] | None = Field(default_factory=list)
    exclude_ids: list[UUID] = Field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = "RUB"
    english_level: str | None = None
    about_me: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("must_skills", "nice_skills", mode="before")
    @classmethod
    def normalize_skills(cls, v: Any) -> list[dict[str, Any]]:
        if not v:
            return []
        if isinstance(v, str):
            return [{"skill": s.strip().lower(), "level": 3} for s in v.split(",") if s.strip()]

        normalized = []
        for item in v:
            if isinstance(item, str):
                normalized.append({"skill": item.strip().lower(), "level": 3})
            elif isinstance(item, dict) and "skill" in item:
                item["skill"] = item["skill"].strip().lower()
                if "level" not in item:
                    item["level"] = 3
                normalized.append(item)
        return normalized


class NextCandidateRequest(BaseModel):
    session_id: UUID
    filters: SearchFilters
    session_exclude_ids: list[UUID] = Field(default_factory=list)


class CandidatePreview(BaseModel):
    id: UUID
    display_name: str
    headline_role: str
    experience_years: float
    location: str | None
    skills: list[str | dict[str, Any]] = Field(default_factory=list)
    match_score: float = 0.0
    explanation: dict[str, float] | None = None
    english_level: str | None = None
    about_me: str | None = None

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
    candidate: CandidatePreview | None
