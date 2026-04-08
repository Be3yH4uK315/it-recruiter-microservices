from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.search.entities import IndexedCandidateDocument


@dataclass(slots=True, frozen=True)
class CandidateSearchHitView:
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


@dataclass(slots=True, frozen=True)
class SearchCandidatesView:
    total: int
    items: list[CandidateSearchHitView]


@dataclass(slots=True, frozen=True)
class IndexedCandidateDocumentView:
    candidate_id: UUID
    searchable_text: str
    document: dict[str, Any]
    vector_present: bool
    vector_store: str

    @classmethod
    def from_entity(cls, entity: IndexedCandidateDocument) -> "IndexedCandidateDocumentView":
        return cls(
            candidate_id=entity.candidate_id,
            searchable_text=entity.searchable_text,
            document=entity.document,
            vector_present=entity.vector_present,
            vector_store=entity.vector_store,
        )


@dataclass(slots=True, frozen=True)
class RebuildIndicesView:
    processed: int
    indexed: int
    skipped: int
    failed: int
