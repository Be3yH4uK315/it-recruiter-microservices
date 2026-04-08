from __future__ import annotations

from uuid import uuid4

from app.application.common.contracts import CandidateDocumentPayload
from app.application.search.services.indexing import DefaultCandidateIndexingService


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.calls = []

    async def encode_text(self, text):
        self.calls.append(text)
        return [0.1, 0.2, 0.3]


async def test_indexing_service_builds_indexed_document() -> None:
    service = DefaultCandidateIndexingService(
        embedding_provider=FakeEmbeddingProvider(),
    )

    payload = CandidateDocumentPayload(
        id=uuid4(),
        display_name="Ivan",
        headline_role="Python Developer",
        location="Paris",
        work_modes=["remote"],
        experience_years=4.0,
        skills=[{"skill": "python", "level": 5}],
        salary_min=100000,
        salary_max=150000,
        currency="RUB",
        english_level="B2",
        about_me="Async backend engineer",
        experiences=[],
        projects=[],
        education=[],
        status="active",
    )

    result = await service.build_indexed_document(payload=payload)

    assert result.candidate_id == payload.id
    assert result.embedding == [0.1, 0.2, 0.3]
    assert result.document["display_name"] == "Ivan"
    assert result.document["headline_role"] == "Python Developer"
    assert result.document["salary_min_rub"] == 100000.0
    assert result.document["salary_max_rub"] == 150000.0
    assert "Python Developer" in result.searchable_text


async def test_indexing_service_normalizes_skill_items() -> None:
    service = DefaultCandidateIndexingService(
        embedding_provider=FakeEmbeddingProvider(),
    )

    payload = CandidateDocumentPayload(
        id=uuid4(),
        display_name="Test",
        headline_role="Backend Engineer",
        location=None,
        work_modes=[],
        experience_years=0.0,
        skills=[
            "Python",
            {"skill": "FastAPI", "level": 4, "kind": "hard"},
            {"name": "Docker"},
        ],
        salary_min=None,
        salary_max=None,
        currency="RUB",
        english_level=None,
        about_me=None,
        experiences=[],
        projects=[],
        education=[],
        status=None,
    )

    result = await service.build_indexed_document(payload=payload)

    assert result.document["skills"] == [
        {"skill": "python"},
        {"skill": "fastapi", "level": 4, "kind": "hard"},
        {"skill": "docker"},
    ]


async def test_indexing_service_reuses_embedding_for_same_searchable_text() -> None:
    embedding_provider = FakeEmbeddingProvider()
    service = DefaultCandidateIndexingService(
        embedding_provider=embedding_provider,
        embedding_cache_size=8,
    )

    common_payload = {
        "headline_role": "Backend Engineer",
        "location": "Novosibirsk",
        "work_modes": ["remote"],
        "experience_years": 4.0,
        "skills": [{"skill": "python", "level": 5}],
        "salary_min": 100000,
        "salary_max": 150000,
        "currency": "RUB",
        "english_level": "B2",
        "about_me": "Async backend engineer",
        "experiences": [],
        "projects": [],
        "education": [],
        "status": "active",
    }

    first_payload = CandidateDocumentPayload(
        id=uuid4(),
        display_name="Candidate One",
        **common_payload,
    )
    second_payload = CandidateDocumentPayload(
        id=uuid4(),
        display_name="Candidate Two",
        **common_payload,
    )

    first_result = await service.build_indexed_document(payload=first_payload)
    second_result = await service.build_indexed_document(payload=second_payload)

    assert first_result.searchable_text == second_result.searchable_text
    assert embedding_provider.calls == [first_result.searchable_text]
