from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.application.search.commands.rebuild_indices import RebuildIndicesCommand
from app.application.search.dto.views import (
    CandidateSearchHitView,
    IndexedCandidateDocumentView,
    RebuildIndicesView,
    SearchCandidatesView,
)
from app.application.search.queries.search_candidates import (
    SearchCandidatesQuery,
    SkillInput,
)
from app.domain.search.enums import WorkMode


class SearchSkillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str
    level: int | None = Field(default=None, ge=1, le=5)

    @field_validator("skill")
    @classmethod
    def validate_skill(cls, value: str) -> str:
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
    def validate_role(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("role must contain at least 2 characters")
        return normalized

    @field_validator("location", "currency", "english_level", "about_me")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
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


class SearchCandidatesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filters: SearchFiltersRequest
    limit: int = Field(default=20, ge=1, le=100)

    def to_query(self) -> SearchCandidatesQuery:
        return SearchCandidatesQuery(
            role=self.filters.role,
            must_skills=[item.to_input() for item in self.filters.must_skills],
            nice_skills=[item.to_input() for item in self.filters.nice_skills],
            experience_min=self.filters.experience_min,
            experience_max=self.filters.experience_max,
            location=self.filters.location,
            work_modes=list(self.filters.work_modes),
            salary_min=self.filters.salary_min,
            salary_max=self.filters.salary_max,
            currency=self.filters.currency,
            english_level=self.filters.english_level,
            exclude_ids=self.filters.exclude_ids,
            about_me=self.filters.about_me,
            limit=self.limit,
        )


class CandidateSearchHitResponse(BaseModel):
    candidate_id: UUID
    display_name: str
    headline_role: str
    experience_years: float
    location: str | None
    skills: list[dict[str, Any] | str]
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    english_level: str | None
    about_me: str | None
    match_score: float
    explanation: dict[str, Any] | None = None

    @classmethod
    def from_view(cls, view: CandidateSearchHitView) -> "CandidateSearchHitResponse":
        return cls(
            candidate_id=view.candidate_id,
            display_name=view.display_name,
            headline_role=view.headline_role,
            experience_years=view.experience_years,
            location=view.location,
            skills=view.skills,
            salary_min=view.salary_min,
            salary_max=view.salary_max,
            currency=view.currency,
            english_level=view.english_level,
            about_me=view.about_me,
            match_score=view.match_score,
            explanation=view.explanation,
        )


class SearchCandidatesResponse(BaseModel):
    total: int
    items: list[CandidateSearchHitResponse]

    @classmethod
    def from_view(cls, view: SearchCandidatesView) -> "SearchCandidatesResponse":
        return cls(
            total=view.total,
            items=[CandidateSearchHitResponse.from_view(item) for item in view.items],
        )


class RebuildIndicesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_size: int = Field(default=100, ge=1, le=1000)

    def to_command(self) -> RebuildIndicesCommand:
        return RebuildIndicesCommand(batch_size=self.batch_size)


class RebuildIndicesResponse(BaseModel):
    processed: int
    indexed: int
    skipped: int
    failed: int

    @classmethod
    def from_view(cls, view: RebuildIndicesView) -> "RebuildIndicesResponse":
        return cls(
            processed=view.processed,
            indexed=view.indexed,
            skipped=view.skipped,
            failed=view.failed,
        )


class IndexedCandidateDocumentResponse(BaseModel):
    candidate_id: UUID
    searchable_text: str
    document: dict[str, Any]
    vector_present: bool
    vector_store: str

    @classmethod
    def from_view(
        cls,
        view: IndexedCandidateDocumentView,
    ) -> "IndexedCandidateDocumentResponse":
        return cls(
            candidate_id=view.candidate_id,
            searchable_text=view.searchable_text,
            document=view.document,
            vector_present=view.vector_present,
            vector_store=view.vector_store,
        )


class UpsertCandidateDocumentResponse(BaseModel):
    candidate_id: UUID
    searchable_text: str
    document: dict[str, Any]
    vector_present: bool
    vector_store: str

    @classmethod
    def from_view(
        cls,
        view: IndexedCandidateDocumentView,
    ) -> "UpsertCandidateDocumentResponse":
        return cls(
            candidate_id=view.candidate_id,
            searchable_text=view.searchable_text,
            document=view.document,
            vector_present=view.vector_present,
            vector_store=view.vector_store,
        )


class DeleteCandidateDocumentResponse(BaseModel):
    deleted: bool
