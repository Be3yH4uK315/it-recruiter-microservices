from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.application.common.ttl_cache import TtlCache
from app.application.common.uow import UnitOfWork
from app.domain.candidate.entities import CandidateProfile
from app.domain.candidate.enums import CandidateStatus
from app.domain.candidate.errors import CandidateNotFoundError


@dataclass(slots=True, frozen=True)
class CandidateSearchDocumentView:
    id: UUID
    telegram_id: int
    display_name: str
    headline_role: str
    location: str | None
    work_modes: list[str]
    contacts_visibility: str
    status: str
    english_level: str | None
    about_me: str | None
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    skills: list[dict[str, Any]]
    education: list[dict[str, Any]]
    experiences: list[dict[str, Any]]
    projects: list[dict[str, Any]]
    avatar_file_id: str | None
    resume_file_id: str | None
    created_at: str | None
    updated_at: str | None
    version_id: int

    @classmethod
    def from_candidate(cls, candidate: CandidateProfile) -> "CandidateSearchDocumentView":
        salary_range = candidate.salary_range

        return cls(
            id=candidate.id,
            telegram_id=candidate.telegram_id,
            display_name=candidate.display_name,
            headline_role=candidate.headline_role,
            location=candidate.location,
            work_modes=[item.value for item in candidate.work_modes],
            contacts_visibility=candidate.contacts_visibility.value,
            status=candidate.status.value,
            english_level=candidate.english_level.value if candidate.english_level else None,
            about_me=candidate.about_me,
            salary_min=salary_range.min_amount if salary_range is not None else None,
            salary_max=salary_range.max_amount if salary_range is not None else None,
            currency=salary_range.currency if salary_range is not None else None,
            skills=[
                {
                    "skill": item.skill,
                    "kind": item.kind.value,
                    "level": item.level,
                }
                for item in candidate.skills
            ],
            education=[
                {
                    "level": item.level,
                    "institution": item.institution,
                    "year": item.year,
                }
                for item in candidate.education
            ],
            experiences=[
                {
                    "company": item.company,
                    "position": item.position,
                    "start_date": item.start_date.isoformat(),
                    "end_date": item.end_date.isoformat() if item.end_date else None,
                    "responsibilities": item.responsibilities,
                }
                for item in candidate.experiences
            ],
            projects=[
                {
                    "title": item.title,
                    "description": item.description,
                    "links": list(item.links),
                }
                for item in candidate.projects
            ],
            avatar_file_id=str(candidate.avatar.file_id) if candidate.avatar is not None else None,
            resume_file_id=str(candidate.resume.file_id) if candidate.resume is not None else None,
            created_at=candidate.created_at.isoformat() if candidate.created_at else None,
            updated_at=candidate.updated_at.isoformat() if candidate.updated_at else None,
            version_id=candidate.version_id,
        )


_SEARCH_DOCUMENT_CACHE = TtlCache[UUID, CandidateSearchDocumentView]()


def clear_candidate_search_document_cache() -> None:
    _SEARCH_DOCUMENT_CACHE.clear()


class GetCandidateSearchDocumentHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        cache_ttl_seconds: float = 0.0,
    ) -> None:
        self._uow_factory = uow_factory
        self._cache_ttl_seconds = cache_ttl_seconds

    async def __call__(self, candidate_id: UUID) -> CandidateSearchDocumentView:
        cached = _SEARCH_DOCUMENT_CACHE.get(candidate_id)
        if cached is not None:
            return cached

        async with self._uow_factory() as uow:
            candidate = await uow.candidates.get_by_id(candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate {candidate_id} not found")

            if candidate.status != CandidateStatus.ACTIVE:
                raise CandidateNotFoundError(f"candidate {candidate_id} not found")

            result = CandidateSearchDocumentView.from_candidate(candidate)

        _SEARCH_DOCUMENT_CACHE.set(
            candidate_id,
            result,
            ttl_seconds=self._cache_ttl_seconds,
        )
        return result
