from __future__ import annotations

from app.application.common.contracts import HybridSearchResult
from app.application.search.services.hybrid_search import DefaultHybridSearchService


class FakeLexicalRepository:
    def __init__(self) -> None:
        self.search_calls = []
        self.documents_calls = []
        self.return_ids = ["c1", "c2", "c3"]
        self.return_documents = [
            {
                "id": "c1",
                "headline_role": "Python Developer",
                "searchable_text": "python fastapi",
                "skills": [{"skill": "python"}, {"skill": "fastapi"}],
            },
            {
                "id": "c2",
                "headline_role": "Backend Engineer",
                "searchable_text": "go postgres",
                "skills": [{"skill": "go"}, {"skill": "postgres"}],
            },
        ]

    async def search_candidate_ids(self, *, filters: dict, limit: int) -> list[str]:
        self.search_calls.append((filters, limit))
        return self.return_ids

    async def count_candidates(self, *, filters: dict) -> int:
        _ = filters
        return len(self.return_ids)

    async def get_documents(self, candidate_ids: list[str]) -> list[dict]:
        self.documents_calls.append(candidate_ids)
        by_id = {item["id"]: item for item in self.return_documents}
        return [by_id[item] for item in candidate_ids if item in by_id]


class FakeVectorRepository:
    def __init__(self) -> None:
        self.calls = []
        self.return_ids = ["c2", "c1"]

    async def search_candidate_ids(
        self,
        *,
        query_vector: list[float],
        exclude_ids: list,
        limit: int,
    ) -> list[str]:
        self.calls.append((query_vector, exclude_ids, limit))
        return self.return_ids


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.calls = []

    async def encode_text(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1, 0.2, 0.3]


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
        result = []
        for idx, item in enumerate(candidates):
            enriched = dict(item)
            enriched["match_score"] = float(len(candidates) - idx)
            enriched["score_explanation"] = {"source": "fake-ranker"}
            result.append(enriched)
        return result


async def test_hybrid_search_combines_sources_and_reranks() -> None:
    lexical = FakeLexicalRepository()
    vector = FakeVectorRepository()
    embedding = FakeEmbeddingProvider()
    ranker = FakeRanker()

    service = DefaultHybridSearchService(
        lexical_repository=lexical,
        vector_repository=vector,
        embedding_provider=embedding,
        ranker=ranker,
        retrieval_size=10,
        rerank_top_k=5,
        rrf_k=60,
    )

    result = await service.search(
        filters={
            "role": "Python Developer",
            "must_skills": [{"skill": "python", "level": 5}],
            "nice_skills": [{"skill": "fastapi", "level": 4}],
            "location": "Paris",
            "english_level": "B2",
            "about_me": "async microservices",
            "exclude_ids": [],
        },
        limit=2,
    )

    assert len(result.items) == 1
    assert lexical.search_calls
    assert vector.calls
    assert embedding.calls
    assert ranker.calls
    assert result.items[0]["id"] == "c1"


async def test_hybrid_search_returns_empty_when_no_fused_results() -> None:
    lexical = FakeLexicalRepository()
    lexical.return_ids = []

    vector = FakeVectorRepository()
    vector.return_ids = []

    embedding = FakeEmbeddingProvider()
    ranker = FakeRanker()

    service = DefaultHybridSearchService(
        lexical_repository=lexical,
        vector_repository=vector,
        embedding_provider=embedding,
        ranker=ranker,
        retrieval_size=10,
        rerank_top_k=5,
        rrf_k=60,
    )

    result = await service.search(
        filters={
            "role": "Python Developer",
            "must_skills": [],
            "nice_skills": [],
            "exclude_ids": [],
        },
        limit=5,
    )

    assert result == HybridSearchResult(total=0, items=[])


async def test_hybrid_search_returns_empty_when_documents_missing() -> None:
    lexical = FakeLexicalRepository()
    lexical.return_documents = []

    vector = FakeVectorRepository()
    embedding = FakeEmbeddingProvider()
    ranker = FakeRanker()

    service = DefaultHybridSearchService(
        lexical_repository=lexical,
        vector_repository=vector,
        embedding_provider=embedding,
        ranker=ranker,
        retrieval_size=10,
        rerank_top_k=5,
        rrf_k=60,
    )

    result = await service.search(
        filters={
            "role": "Python Developer",
            "must_skills": [],
            "nice_skills": [],
            "exclude_ids": [],
        },
        limit=5,
    )

    assert result == HybridSearchResult(total=3, items=[])


async def test_hybrid_search_builds_query_text() -> None:
    service = DefaultHybridSearchService(
        lexical_repository=FakeLexicalRepository(),
        vector_repository=FakeVectorRepository(),
        embedding_provider=FakeEmbeddingProvider(),
        ranker=FakeRanker(),
        retrieval_size=10,
        rerank_top_k=5,
        rrf_k=60,
    )

    query_text = service._build_query_text(
        {
            "role": "Python Developer",
            "must_skills": [{"skill": "python"}],
            "nice_skills": [{"skill": "fastapi"}],
            "location": "Paris",
            "english_level": "B2",
            "about_me": "async services",
        }
    )

    assert "Python Developer" in query_text
    assert "python" in query_text
    assert "fastapi" in query_text
    assert "Paris" in query_text
    assert "B2" in query_text
    assert "async services" in query_text


async def test_hybrid_search_extracts_valid_exclude_ids() -> None:
    from uuid import uuid4

    valid_id = uuid4()

    service = DefaultHybridSearchService(
        lexical_repository=FakeLexicalRepository(),
        vector_repository=FakeVectorRepository(),
        embedding_provider=FakeEmbeddingProvider(),
        ranker=FakeRanker(),
        retrieval_size=10,
        rerank_top_k=5,
        rrf_k=60,
    )

    result = service._extract_exclude_ids({"exclude_ids": [str(valid_id), "bad-uuid", valid_id]})

    assert valid_id in result
    assert len(result) == 1


async def test_hybrid_search_caches_query_embeddings() -> None:
    lexical = FakeLexicalRepository()
    vector = FakeVectorRepository()
    embedding = FakeEmbeddingProvider()
    ranker = FakeRanker()

    service = DefaultHybridSearchService(
        lexical_repository=lexical,
        vector_repository=vector,
        embedding_provider=embedding,
        ranker=ranker,
        retrieval_size=10,
        rerank_top_k=5,
        rrf_k=60,
    )

    filters = {
        "role": "Python Developer",
        "must_skills": [{"skill": "python"}],
        "nice_skills": [],
        "exclude_ids": [],
    }

    await service.search(filters=filters, limit=2)
    await service.search(filters=filters, limit=2)

    assert embedding.calls == ["Python Developer skills: python"]


async def test_hybrid_search_caches_repeated_results() -> None:
    lexical = FakeLexicalRepository()
    vector = FakeVectorRepository()
    embedding = FakeEmbeddingProvider()
    ranker = FakeRanker()

    service = DefaultHybridSearchService(
        lexical_repository=lexical,
        vector_repository=vector,
        embedding_provider=embedding,
        ranker=ranker,
        retrieval_size=10,
        rerank_top_k=5,
        rrf_k=60,
        result_cache_ttl_seconds=60.0,
    )

    filters = {
        "role": "Python Developer",
        "must_skills": [{"skill": "python"}],
        "nice_skills": [],
        "exclude_ids": [],
    }

    first = await service.search(filters=filters, limit=2)
    second = await service.search(filters=filters, limit=2)

    assert first == second
    assert len(lexical.search_calls) == 1
    assert len(vector.calls) == 1
    assert len(ranker.calls) == 1


async def test_hybrid_search_limits_rerank_window_relative_to_requested_limit() -> None:
    lexical = FakeLexicalRepository()
    lexical.return_ids = [f"c{i}" for i in range(1, 11)]
    lexical.return_documents = [
        {
            "id": f"c{i}",
            "headline_role": f"Candidate {i}",
            "searchable_text": "python fastapi",
            "skills": [{"skill": "python"}],
        }
        for i in range(1, 11)
    ]
    vector = FakeVectorRepository()
    vector.return_ids = [f"c{i}" for i in range(10, 0, -1)]
    embedding = FakeEmbeddingProvider()
    ranker = FakeRanker()

    service = DefaultHybridSearchService(
        lexical_repository=lexical,
        vector_repository=vector,
        embedding_provider=embedding,
        ranker=ranker,
        retrieval_size=10,
        rerank_top_k=10,
        rrf_k=60,
    )

    await service.search(
        filters={
            "role": "Python Developer",
            "must_skills": [],
            "nice_skills": [],
            "exclude_ids": [],
        },
        limit=3,
    )

    assert ranker.calls
    _, rerank_candidates, _ = ranker.calls[0]
    assert len(rerank_candidates) == 5


async def test_hybrid_search_hard_filters_required_skill_levels_after_fusion() -> None:
    lexical = FakeLexicalRepository()
    lexical.return_ids = ["c1"]
    lexical.return_documents = [
        {
            "id": "c1",
            "headline_role": "Python Developer",
            "searchable_text": "python backend",
            "skills": [{"skill": "python", "level": 3}],
        }
    ]
    vector = FakeVectorRepository()
    vector.return_ids = ["c1"]
    embedding = FakeEmbeddingProvider()
    ranker = FakeRanker()

    service = DefaultHybridSearchService(
        lexical_repository=lexical,
        vector_repository=vector,
        embedding_provider=embedding,
        ranker=ranker,
        retrieval_size=10,
        rerank_top_k=5,
        rrf_k=60,
    )

    result = await service.search(
        filters={
            "role": "Python Developer",
            "must_skills": [{"skill": "python", "level": 5}],
            "nice_skills": [],
            "exclude_ids": [],
        },
        limit=5,
    )

    assert result == HybridSearchResult(total=1, items=[])
    assert ranker.calls == []


async def test_hybrid_search_hard_filters_work_mode_compatibility_after_fusion() -> None:
    lexical = FakeLexicalRepository()
    lexical.return_ids = ["c1"]
    lexical.return_documents = [
        {
            "id": "c1",
            "headline_role": "Python Developer",
            "searchable_text": "python backend",
            "skills": [{"skill": "python", "level": 5}],
            "work_modes": ["onsite"],
            "status": "active",
        }
    ]
    vector = FakeVectorRepository()
    vector.return_ids = ["c1"]
    embedding = FakeEmbeddingProvider()
    ranker = FakeRanker()

    service = DefaultHybridSearchService(
        lexical_repository=lexical,
        vector_repository=vector,
        embedding_provider=embedding,
        ranker=ranker,
        retrieval_size=10,
        rerank_top_k=5,
        rrf_k=60,
    )

    result = await service.search(
        filters={
            "role": "Python Developer",
            "must_skills": [{"skill": "python", "level": 5}],
            "nice_skills": [],
            "work_modes": ["remote"],
            "exclude_ids": [],
        },
        limit=5,
    )

    assert result == HybridSearchResult(total=1, items=[])
    assert ranker.calls == []


async def test_hybrid_search_hard_filters_salary_compatibility_after_fusion() -> None:
    lexical = FakeLexicalRepository()
    lexical.return_ids = ["c1"]
    lexical.return_documents = [
        {
            "id": "c1",
            "headline_role": "Python Developer",
            "searchable_text": "python backend",
            "skills": [{"skill": "python", "level": 5}],
            "salary_min_rub": 500000.0,
            "salary_max_rub": 700000.0,
            "status": "active",
        }
    ]
    vector = FakeVectorRepository()
    vector.return_ids = ["c1"]
    embedding = FakeEmbeddingProvider()
    ranker = FakeRanker()

    service = DefaultHybridSearchService(
        lexical_repository=lexical,
        vector_repository=vector,
        embedding_provider=embedding,
        ranker=ranker,
        retrieval_size=10,
        rerank_top_k=5,
        rrf_k=60,
    )

    result = await service.search(
        filters={
            "role": "Python Developer",
            "must_skills": [{"skill": "python", "level": 5}],
            "nice_skills": [],
            "salary_min": 100000,
            "salary_max": 300000,
            "currency": "RUB",
            "exclude_ids": [],
        },
        limit=5,
    )

    assert result == HybridSearchResult(total=1, items=[])
    assert ranker.calls == []
