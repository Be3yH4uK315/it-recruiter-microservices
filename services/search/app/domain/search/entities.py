from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(slots=True, frozen=True)
class CandidateSearchResult:
    candidate_id: UUID
    match_score: float
    explanation: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class IndexedCandidateDocument:
    candidate_id: UUID
    document: dict[str, Any]
    searchable_text: str
    embedding: list[float] = field(default_factory=list)
    vector_present: bool = False
    vector_store: str = "milvus"
