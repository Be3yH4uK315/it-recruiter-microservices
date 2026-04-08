from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.application.common.contracts import CandidateDocumentPayload
from app.application.search.queries.search_candidates import (
    SearchCandidatesHandler,
    SearchCandidatesQuery,
    SkillInput,
)
from app.application.search.services.hybrid_search import DefaultHybridSearchService
from app.application.search.services.indexing import DefaultCandidateIndexingService
from app.domain.search.enums import WorkMode


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.calls = []

    async def encode_text(self, text: str) -> list[float]:
        self.calls.append(text)
        lowered = text.lower()
        if "python" in lowered and "fastapi" in lowered:
            return [1.0, 0.0, 0.0]
        if "python" in lowered:
            return [0.9, 0.0, 0.0]
        if "go" in lowered:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    async def encode_many(self, texts: list[str]) -> list[list[float]]:
        return [await self.encode_text(text) for text in texts]


class InMemoryLexicalRepository:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}

    async def search_candidate_ids(self, *, filters: dict, limit: int) -> list[str]:
        role = str(filters.get("role") or "").strip().lower()
        must_skills = {
            str(item.get("skill") or "").strip().lower()
            for item in (filters.get("must_skills") or [])
            if isinstance(item, dict)
        }
        results: list[str] = []

        for candidate_id, doc in self.documents.items():
            headline_role = str(doc.get("headline_role") or "").lower()
            doc_skills = {
                str(item.get("skill") or "").strip().lower()
                for item in (doc.get("skills") or [])
                if isinstance(item, dict)
            }

            if role and role not in headline_role:
                continue
            if must_skills and not must_skills.issubset(doc_skills):
                continue

            results.append(candidate_id)

        return results[:limit]

    async def count_candidates(self, *, filters: dict) -> int:
        return len(await self.search_candidate_ids(filters=filters, limit=10_000))

    async def get_documents(self, candidate_ids: list[str]) -> list[dict]:
        return [
            self.documents[candidate_id]
            for candidate_id in candidate_ids
            if candidate_id in self.documents
        ]

    async def get_document(self, candidate_id: UUID) -> dict | None:
        return self.documents.get(str(candidate_id))

    async def upsert_document(self, *, candidate_id: UUID, document: dict) -> None:
        self.documents[str(candidate_id)] = document

    async def delete_document(self, *, candidate_id: UUID) -> None:
        self.documents.pop(str(candidate_id), None)


class InMemoryVectorRepository:
    def __init__(self) -> None:
        self.vectors: dict[str, list[float]] = {}

    async def search_candidate_ids(
        self,
        *,
        query_vector: list[float],
        exclude_ids: list[UUID],
        limit: int,
    ) -> list[str]:
        excluded = {str(item) for item in exclude_ids}

        def dot(v1: list[float], v2: list[float]) -> float:
            return sum(a * b for a, b in zip(v1, v2, strict=False))

        scored: list[tuple[str, float]] = []
        for candidate_id, vector in self.vectors.items():
            if candidate_id in excluded:
                continue
            scored.append((candidate_id, dot(query_vector, vector)))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [candidate_id for candidate_id, _ in scored[:limit]]

    async def upsert_vector(self, *, candidate_id: UUID, embedding: list[float]) -> None:
        self.vectors[str(candidate_id)] = embedding

    async def delete_vector(self, *, candidate_id: UUID) -> None:
        self.vectors.pop(str(candidate_id), None)


class FakeRanker:
    def __init__(self) -> None:
        self.calls = []

    async def rerank(
        self,
        *,
        query_text: str,
        candidates: list[dict],
        filters: dict,
    ) -> list[dict]:
        self.calls.append((query_text, candidates, filters))
        ranked: list[dict] = []

        for item in candidates:
            score = 0.1
            searchable_text = str(item.get("searchable_text") or "").lower()

            if "python" in searchable_text:
                score += 1.0
            if "fastapi" in searchable_text:
                score += 1.0
            if "go" in searchable_text:
                score -= 0.5

            enriched = dict(item)
            enriched["match_score"] = score
            enriched["score_explanation"] = {"source": "fake-ranker", "raw_score": score}
            ranked.append(enriched)

        ranked.sort(key=lambda item: item["match_score"], reverse=True)
        return ranked


def make_payload(
    *,
    candidate_id: UUID,
    display_name: str,
    headline_role: str,
    skills,
    about_me: str,
) -> CandidateDocumentPayload:
    return CandidateDocumentPayload(
        id=candidate_id,
        display_name=display_name,
        headline_role=headline_role,
        location="Paris",
        work_modes=["remote"],
        experience_years=4.0,
        skills=skills,
        salary_min=100000,
        salary_max=180000,
        currency="RUB",
        english_level="B2",
        about_me=about_me,
        experiences=[],
        projects=[],
        education=[],
        status="active",
    )


@pytest.mark.asyncio
async def test_search_pipeline_indexes_and_finds_best_candidate() -> None:
    embedding_provider = FakeEmbeddingProvider()
    lexical_repository = InMemoryLexicalRepository()
    vector_repository = InMemoryVectorRepository()
    ranker = FakeRanker()

    indexing_service = DefaultCandidateIndexingService(
        embedding_provider=embedding_provider,
    )

    python_candidate_id = uuid4()
    go_candidate_id = uuid4()

    python_candidate = make_payload(
        candidate_id=python_candidate_id,
        display_name="Ivan Python",
        headline_role="Python Developer",
        skills=[{"skill": "python"}, {"skill": "fastapi"}],
        about_me="Builds async Python APIs with FastAPI",
    )
    go_candidate = make_payload(
        candidate_id=go_candidate_id,
        display_name="Petr Go",
        headline_role="Backend Engineer",
        skills=[{"skill": "go"}, {"skill": "grpc"}],
        about_me="Builds backend services in Go",
    )

    for payload in (python_candidate, go_candidate):
        indexed = await indexing_service.build_indexed_document(payload=payload)
        await lexical_repository.upsert_document(
            candidate_id=indexed.candidate_id,
            document=indexed.document,
        )
        await vector_repository.upsert_vector(
            candidate_id=indexed.candidate_id,
            embedding=indexed.embedding,
        )

    hybrid_search_service = DefaultHybridSearchService(
        lexical_repository=lexical_repository,
        vector_repository=vector_repository,
        embedding_provider=embedding_provider,
        ranker=ranker,
        retrieval_size=10,
        rerank_top_k=10,
        rrf_k=60,
    )

    handler = SearchCandidatesHandler(hybrid_search_service=hybrid_search_service)

    result = await handler(
        SearchCandidatesQuery(
            role="Python Developer",
            must_skills=[SkillInput(skill="Python", level=5)],
            nice_skills=[SkillInput(skill="FastAPI", level=4)],
            location="Paris",
            work_modes=[WorkMode.REMOTE],
            limit=5,
        )
    )

    assert result.total >= 1
    assert result.items[0].candidate_id == python_candidate_id
    assert result.items[0].display_name == "Ivan Python"
    assert result.items[0].headline_role == "Python Developer"
    assert result.items[0].match_score > 0
    assert ranker.calls
    assert str(python_candidate_id) in lexical_repository.documents
    assert str(python_candidate_id) in vector_repository.vectors
