from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.application.common.contracts import HybridSearchService
from app.application.search.dto.views import (
    CandidateSearchHitView,
    SearchCandidatesView,
)
from app.domain.search.enums import WorkMode
from app.domain.search.value_objects import SalaryRange, SearchFilters, SearchSkill


@dataclass(slots=True, frozen=True)
class SkillInput:
    skill: str
    level: int | None = None


@dataclass(slots=True, frozen=True)
class SearchCandidatesQuery:
    role: str
    must_skills: list[SkillInput] = field(default_factory=list)
    nice_skills: list[SkillInput] = field(default_factory=list)
    experience_min: float | None = None
    experience_max: float | None = None
    location: str | None = None
    work_modes: list[WorkMode] = field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    english_level: str | None = None
    exclude_ids: list[UUID] = field(default_factory=list)
    about_me: str | None = None
    limit: int = 20
    include_total: bool = True


class SearchCandidatesHandler:
    def __init__(self, hybrid_search_service: HybridSearchService) -> None:
        self._hybrid_search_service = hybrid_search_service

    async def __call__(self, query: SearchCandidatesQuery) -> SearchCandidatesView:
        filters = SearchFilters(
            role=query.role,
            must_skills=tuple(
                SearchSkill(skill=item.skill, level=item.level) for item in query.must_skills
            ),
            nice_skills=tuple(
                SearchSkill(skill=item.skill, level=item.level) for item in query.nice_skills
            ),
            experience_min=query.experience_min,
            experience_max=query.experience_max,
            location=query.location,
            work_modes=tuple(query.work_modes),
            salary_range=SalaryRange.from_scalars(
                salary_min=query.salary_min,
                salary_max=query.salary_max,
                currency=query.currency,
            ),
            english_level=query.english_level,
            exclude_ids=tuple(query.exclude_ids),
            about_me=query.about_me,
        )

        search_result = await self._hybrid_search_service.search(
            filters=filters.to_primitives(),
            limit=query.limit,
            include_total=query.include_total,
        )

        items: list[CandidateSearchHitView] = []
        for item in search_result.items:
            raw_id = item.get("id")
            if raw_id is None:
                continue

            try:
                candidate_id = UUID(str(raw_id))
            except ValueError:
                continue

            explanation = item.get("score_explanation")
            if not isinstance(explanation, dict):
                explanation = (
                    item.get("explanation") if isinstance(item.get("explanation"), dict) else None
                )

            skills = item.get("skills")
            if not isinstance(skills, list):
                skills = []

            items.append(
                CandidateSearchHitView(
                    candidate_id=candidate_id,
                    display_name=str(item.get("display_name") or "Candidate"),
                    headline_role=str(item.get("headline_role") or ""),
                    experience_years=float(item.get("experience_years") or 0.0),
                    location=item.get("location"),
                    skills=skills,
                    salary_min=item.get("salary_min"),
                    salary_max=item.get("salary_max"),
                    currency=item.get("currency"),
                    english_level=item.get("english_level"),
                    about_me=item.get("about_me"),
                    match_score=float(item.get("match_score") or 0.0),
                    explanation=explanation,
                )
            )

        return SearchCandidatesView(
            total=search_result.total,
            items=items,
        )
