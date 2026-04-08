from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.domain.search.entities import IndexedCandidateDocument


@dataclass(slots=True, frozen=True)
class CandidateDocumentPayload:
    id: UUID
    display_name: str
    headline_role: str
    location: str | None
    work_modes: list[str]
    experience_years: float
    skills: list[dict[str, Any] | str]
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    english_level: str | None
    about_me: str | None
    experiences: list[dict[str, Any]] = field(default_factory=list)
    projects: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    status: str | None = None


@dataclass(slots=True, frozen=True)
class SearchHit:
    candidate_id: UUID
    match_score: float
    explanation: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class SearchHealthStatus:
    elasticsearch_ok: bool
    milvus_ok: bool
    embedding_ok: bool
    ranker_ok: bool


@dataclass(slots=True, frozen=True)
class HybridSearchResult:
    total: int
    items: list[dict[str, Any]] = field(default_factory=list)


class CandidateGateway(ABC):
    @abstractmethod
    async def get_candidate_profile(
        self,
        *,
        candidate_id: UUID,
    ) -> CandidateDocumentPayload | None:
        raise NotImplementedError

    @abstractmethod
    async def list_candidates(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[CandidateDocumentPayload]:
        raise NotImplementedError


class EmbeddingProvider(ABC):
    @abstractmethod
    async def encode_text(self, text: str) -> list[float]:
        raise NotImplementedError

    @abstractmethod
    async def encode_many(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class Ranker(ABC):
    @abstractmethod
    async def rerank(
        self,
        *,
        query_text: str,
        candidates: list[dict[str, Any]],
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


class CandidateIndexingService(ABC):
    @abstractmethod
    async def build_indexed_document(
        self,
        *,
        payload: CandidateDocumentPayload,
    ) -> IndexedCandidateDocument:
        raise NotImplementedError


class HybridSearchService(ABC):
    @abstractmethod
    async def search(
        self,
        *,
        filters: dict[str, Any],
        limit: int,
    ) -> HybridSearchResult:
        raise NotImplementedError
