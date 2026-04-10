from __future__ import annotations

from uuid import uuid4

from app.application.common.contracts import HybridSearchResult
from app.application.search.queries.search_candidates import (
    SearchCandidatesHandler,
    SearchCandidatesQuery,
    SkillInput,
)
from app.domain.search.enums import WorkMode


class FakeHybridSearchService:
    def __init__(self, result: HybridSearchResult) -> None:
        self.result = result
        self.calls = []

    async def search(
        self,
        *,
        filters: dict,
        limit: int,
        include_total: bool = True,
    ) -> HybridSearchResult:
        self.calls.append((filters, limit, include_total))
        return self.result


async def test_search_candidates_handler_returns_view() -> None:
    candidate_id = uuid4()
    hybrid = FakeHybridSearchService(
        HybridSearchResult(
            total=1,
            items=[
                {
                    "id": str(candidate_id),
                    "display_name": "Иван",
                    "headline_role": "Python Developer",
                    "experience_years": 4.5,
                    "location": "Paris",
                    "skills": [{"skill": "python"}],
                    "salary_min": 100000,
                    "salary_max": 150000,
                    "currency": "RUB",
                    "english_level": "B2",
                    "about_me": "Async backend",
                    "match_score": 0.98,
                    "score_explanation": {"source": "test"},
                }
            ],
        )
    )
    handler = SearchCandidatesHandler(hybrid_search_service=hybrid)

    result = await handler(
        SearchCandidatesQuery(
            role="Python Developer",
            must_skills=[SkillInput(skill="Python", level=5)],
            nice_skills=[SkillInput(skill="FastAPI", level=4)],
            experience_min=2,
            experience_max=6,
            location="Paris",
            work_modes=[WorkMode.REMOTE],
            salary_min=100000,
            salary_max=200000,
            currency="RUB",
            english_level="B2",
            about_me="Async systems",
            limit=10,
        )
    )

    assert result.total == 1
    assert result.items[0].display_name == "Иван"
    assert result.items[0].headline_role == "Python Developer"
    assert result.items[0].match_score == 0.98
    assert hybrid.calls


async def test_search_candidates_handler_skips_items_without_id() -> None:
    hybrid = FakeHybridSearchService(
        HybridSearchResult(
            total=1,
            items=[
                {
                    "display_name": "No ID Candidate",
                    "match_score": 0.5,
                }
            ],
        )
    )
    handler = SearchCandidatesHandler(hybrid_search_service=hybrid)

    result = await handler(
        SearchCandidatesQuery(
            role="Python Developer",
            limit=5,
        )
    )

    assert result.total == 1
    assert result.items == []


async def test_search_candidates_handler_passes_filters_to_hybrid_service() -> None:
    hybrid = FakeHybridSearchService(HybridSearchResult(total=0, items=[]))
    handler = SearchCandidatesHandler(hybrid_search_service=hybrid)

    query = SearchCandidatesQuery(
        role="Backend Engineer",
        must_skills=[SkillInput(skill="Python", level=5)],
        nice_skills=[SkillInput(skill="Docker", level=3)],
        location="Berlin",
        work_modes=[WorkMode.REMOTE, WorkMode.HYBRID],
        experience_min=3,
        experience_max=7,
        salary_min=120000,
        salary_max=250000,
        currency="EUR",
        english_level="C1",
        about_me="distributed systems",
        limit=7,
    )

    await handler(query)

    assert hybrid.calls
    filters, limit, include_total = hybrid.calls[0]
    assert limit == 7
    assert include_total is True
    assert filters["role"] == "Backend Engineer"
    assert filters["must_skills"] == [{"skill": "python", "level": 5}]
    assert filters["nice_skills"] == [{"skill": "docker", "level": 3}]
    assert filters["location"] == "Berlin"
    assert filters["work_modes"] == ["remote", "hybrid"]
    assert filters["experience_min"] == 3
    assert filters["experience_max"] == 7
    assert filters["salary_min"] == 120000
    assert filters["salary_max"] == 250000
    assert filters["currency"] == "EUR"
    assert filters["english_level"] == "C1"
    assert filters["about_me"] == "distributed systems"
