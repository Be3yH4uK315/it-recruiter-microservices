from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.application.common.contracts import HybridSearchResult
from app.application.search.services.quality_evaluation import (
    SearchEvaluationMode,
    SearchQualityCase,
    SearchQualityEvaluator,
    load_quality_cases,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


class FakeEmbeddingProvider:
    async def encode_text(self, text: str) -> list[float]:
        lowered = text.lower()
        if "python" in lowered and "fastapi" in lowered:
            return [1.0, 0.0]
        if "python" in lowered:
            return [0.8, 0.2]
        return [0.0, 1.0]

    async def encode_many(self, texts: list[str]) -> list[list[float]]:
        return [await self.encode_text(text) for text in texts]


class InMemoryLexicalRepository:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}
        self.lexical_order: list[str] = []

    async def clear_all(self) -> None:
        self.documents.clear()
        self.lexical_order.clear()

    async def list_candidate_ids(self) -> list[str]:
        return list(self.lexical_order)

    async def search_candidate_ids(self, *, filters: dict, limit: int) -> list[str]:
        role = str(filters.get("role") or "").strip().lower()
        result: list[str] = []

        for candidate_id in self.lexical_order:
            doc = self.documents[candidate_id]
            headline_role = str(doc.get("headline_role") or "").strip().lower()
            if role and role not in headline_role:
                continue
            result.append(candidate_id)

        return result[:limit]

    async def count_candidates(self, *, filters: dict) -> int:
        return len(await self.search_candidate_ids(filters=filters, limit=10_000))

    async def get_documents(self, candidate_ids: list[str]) -> list[dict]:
        return [self.documents[item] for item in candidate_ids if item in self.documents]

    async def get_document(self, candidate_id: UUID) -> dict | None:
        return self.documents.get(str(candidate_id))

    async def upsert_document(self, *, candidate_id: UUID, document: dict) -> None:
        normalized_id = str(candidate_id)
        self.documents[normalized_id] = document
        if normalized_id not in self.lexical_order:
            self.lexical_order.append(normalized_id)

    async def delete_document(self, *, candidate_id: UUID) -> None:
        normalized_id = str(candidate_id)
        self.documents.pop(normalized_id, None)
        self.lexical_order = [item for item in self.lexical_order if item != normalized_id]


class InMemoryVectorRepository:
    def __init__(self) -> None:
        self.vectors: dict[str, list[float]] = {}

    async def clear_all(self) -> None:
        self.vectors.clear()

    async def list_candidate_ids(self) -> list[str]:
        return list(self.vectors)

    async def search_candidate_ids(
        self,
        *,
        query_vector: list[float],
        exclude_ids: list[UUID],
        limit: int,
    ) -> list[str]:
        excluded = {str(item) for item in exclude_ids}

        def dot(left: list[float], right: list[float]) -> float:
            return sum(a * b for a, b in zip(left, right, strict=False))

        scored: list[tuple[str, float]] = []
        for candidate_id, vector in self.vectors.items():
            if candidate_id in excluded:
                continue
            scored.append((candidate_id, dot(query_vector, vector)))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [candidate_id for candidate_id, _ in scored[:limit]]

    async def upsert_vector(self, *, candidate_id: UUID, embedding: list[float]) -> None:
        self.vectors[str(candidate_id)] = list(embedding)

    async def delete_vector(self, *, candidate_id: UUID) -> None:
        self.vectors.pop(str(candidate_id), None)

    async def has_vector(self, *, candidate_id: UUID) -> bool:
        return str(candidate_id) in self.vectors


class FakeHybridSearchService:
    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.calls: list[tuple[dict, int, bool]] = []

    async def search(
        self,
        *,
        filters: dict,
        limit: int,
        include_total: bool = True,
    ) -> HybridSearchResult:
        self.calls.append((filters, limit, include_total))
        return HybridSearchResult(total=len(self.items), items=self.items[:limit])


def make_document(
    *,
    candidate_id: UUID,
    headline_role: str,
) -> dict:
    return {
        "id": str(candidate_id),
        "display_name": headline_role,
        "headline_role": headline_role,
        "status": "active",
        "work_modes": ["remote"],
        "experience_years": 4.0,
        "skills": [{"skill": "python", "level": 5}, {"skill": "fastapi", "level": 4}],
        "salary_min_rub": 180000,
        "salary_max_rub": 260000,
    }


def test_quality_metrics_support_binary_and_graded_relevance() -> None:
    ranked_ids = ["a", "b", "c"]
    relevance = {"a": 3.0, "b": 1.0}

    assert precision_at_k(ranked_ids, relevance, k=1) == 1.0
    assert precision_at_k(ranked_ids, relevance, k=2) == 1.0
    assert recall_at_k(ranked_ids, relevance, k=2) == 1.0
    assert reciprocal_rank(ranked_ids, relevance) == 1.0
    assert ndcg_at_k(ranked_ids, relevance, k=2) == 1.0


@pytest.mark.asyncio
async def test_quality_evaluator_compares_modes_and_aggregates_metrics() -> None:
    lexical_repository = InMemoryLexicalRepository()
    vector_repository = InMemoryVectorRepository()
    embedding_provider = FakeEmbeddingProvider()

    lower_relevance_id = uuid4()
    higher_relevance_id = uuid4()
    irrelevant_id = uuid4()

    for candidate_id, title in (
        (lower_relevance_id, "Python Developer"),
        (higher_relevance_id, "Python Developer"),
        (irrelevant_id, "Go Developer"),
    ):
        await lexical_repository.upsert_document(
            candidate_id=candidate_id,
            document=make_document(candidate_id=candidate_id, headline_role=title),
        )

    await vector_repository.upsert_vector(
        candidate_id=lower_relevance_id,
        embedding=[0.1, 0.2],
    )
    await vector_repository.upsert_vector(
        candidate_id=higher_relevance_id,
        embedding=[1.0, 0.0],
    )
    await vector_repository.upsert_vector(
        candidate_id=irrelevant_id,
        embedding=[0.0, 1.0],
    )

    hybrid_search_service = FakeHybridSearchService(
        items=[
            lexical_repository.documents[str(higher_relevance_id)],
            lexical_repository.documents[str(lower_relevance_id)],
        ]
    )

    evaluator = SearchQualityEvaluator(
        lexical_repository=lexical_repository,
        vector_repository=vector_repository,
        embedding_provider=embedding_provider,
        hybrid_search_service=hybrid_search_service,
    )

    report = await evaluator.evaluate(
        cases=[
            SearchQualityCase(
                case_id="python_backend",
                filters={"role": "Python Developer"},
                relevance={
                    str(higher_relevance_id): 3.0,
                    str(lower_relevance_id): 1.0,
                },
            )
        ],
        k_values=[1, 2],
        modes=[
            SearchEvaluationMode.LEXICAL,
            SearchEvaluationMode.VECTOR,
            SearchEvaluationMode.HYBRID,
        ],
    )

    assert report.k_values == [1, 2]
    assert len(report.per_query) == 3
    assert [item.mode for item in report.summaries] == [
        SearchEvaluationMode.LEXICAL,
        SearchEvaluationMode.VECTOR,
        SearchEvaluationMode.HYBRID,
    ]

    lexical_summary = report.summaries[0]
    vector_summary = report.summaries[1]
    hybrid_summary = report.summaries[2]

    assert lexical_summary.precision_at_k[1] == 1.0
    assert lexical_summary.ndcg_at_k[1] < hybrid_summary.ndcg_at_k[1]
    assert vector_summary.recall_at_k[2] == 0.5
    assert hybrid_summary.recall_at_k[2] == 1.0
    assert hybrid_summary.mrr == 1.0
    assert hybrid_search_service.calls


def test_load_quality_cases_supports_dict_and_list_relevance_payloads() -> None:
    k_values, cases = load_quality_cases(
        {
            "k_values": [3, 5],
            "cases": [
                {
                    "id": "graded",
                    "filters": {"role": "Python Developer"},
                    "relevance": {"a": 3, "b": 1},
                },
                {
                    "id": "binary",
                    "filters": {"role": "Go Developer"},
                    "relevance": ["x", "y"],
                },
            ],
        }
    )

    assert k_values == [3, 5]
    assert len(cases) == 2
    assert cases[0].relevance == {"a": 3.0, "b": 1.0}
    assert cases[1].relevance == {"x": 1.0, "y": 1.0}
