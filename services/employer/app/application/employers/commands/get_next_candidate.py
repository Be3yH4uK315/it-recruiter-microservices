from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.application.common.contracts import (
    CandidateGateway,
    CandidateShortProfile,
    SearchGateway,
)
from app.application.common.uow import UnitOfWork
from app.domain.employer.enums import SearchStatus
from app.domain.employer.errors import (
    EmployerNotFoundError,
    SearchSessionClosedError,
    SearchSessionNotFoundError,
    SearchSessionPausedError,
)
from app.domain.employer.value_objects import SearchCandidateSnapshot, SearchSessionCandidate
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)

_SEARCH_BATCH_LIMIT = 50


@dataclass(slots=True, frozen=True)
class NextCandidateResult:
    candidate: CandidateShortProfile | None = None
    message: str | None = None
    is_degraded: bool = False


class GetNextCandidateHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        search_gateway: SearchGateway,
        candidate_gateway: CandidateGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._search_gateway = search_gateway
        self._candidate_gateway = candidate_gateway

    async def __call__(self, session_id: UUID) -> NextCandidateResult:
        async with self._uow_factory() as uow:
            session = await uow.searches.get_by_id(session_id)
            if session is None:
                raise SearchSessionNotFoundError(f"search session {session_id} not found")

            if session.status == SearchStatus.CLOSED:
                raise SearchSessionClosedError("search session is closed")

            if session.status == SearchStatus.PAUSED:
                raise SearchSessionPausedError("search session is paused")

            employer = await uow.employers.get_by_id(session.employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {session.employer_id} not found")

            degraded = False

            while True:
                pool_item = await uow.searches.get_next_pool_candidate(session.id)

                if pool_item is None:
                    refill_result = await self._refill_pool(
                        uow=uow,
                        session_id=session.id,
                    )
                    pool_item = refill_result.pool_item
                    degraded = degraded or refill_result.is_degraded

                    if pool_item is None:
                        message = (
                            "Search service is temporarily unavailable."
                            if degraded
                            else "No more candidates found matching criteria."
                        )
                        return NextCandidateResult(
                            candidate=None,
                            message=message,
                            is_degraded=degraded,
                        )

                candidate = await self._candidate_gateway.get_candidate_profile(
                    candidate_id=pool_item.snapshot.candidate_id,
                    employer_telegram_id=employer.telegram_id,
                )

                if candidate is None:
                    logger.info(
                        "candidate profile is unavailable, skipping pool item",
                        extra={
                            "session_id": str(session.id),
                            "candidate_id": str(pool_item.snapshot.candidate_id),
                        },
                    )
                    await uow.searches.mark_pool_candidate_consumed(
                        session_id=session.id,
                        candidate_id=pool_item.snapshot.candidate_id,
                    )
                    await uow.flush()
                    continue

                enriched_candidate = self._enrich_candidate(candidate, pool_item.snapshot)
                return NextCandidateResult(
                    candidate=enriched_candidate,
                    message=None,
                    is_degraded=degraded,
                )

    @dataclass(slots=True, frozen=True)
    class _RefillResult:
        pool_item: SearchSessionCandidate | None
        is_degraded: bool = False

    async def _refill_pool(
        self,
        *,
        uow: UnitOfWork,
        session_id: UUID,
    ) -> _RefillResult:
        session = await uow.searches.get_by_id(session_id)
        if session is None:
            raise SearchSessionNotFoundError(f"search session {session_id} not found")

        viewed_ids = await uow.searches.list_viewed_candidate_ids(session.id)
        pooled_ids = await uow.searches.list_pool_candidate_ids(session.id)
        merged_filters = session.filters.merge_exclude_ids(viewed_ids, pooled_ids)

        batch = await self._search_gateway.search_candidates(
            filters=merged_filters.to_primitives(),
            limit=_SEARCH_BATCH_LIMIT,
        )

        if not batch.items:
            return self._RefillResult(
                pool_item=None,
                is_degraded=batch.is_degraded,
            )

        pool_items = [
            SearchSessionCandidate(
                id=uuid4(),
                session_id=session.id,
                rank_position=session.search_offset + index,
                snapshot=SearchCandidateSnapshot(
                    candidate_id=item.candidate_id,
                    display_name=item.display_name,
                    headline_role=item.headline_role,
                    experience_years=item.experience_years,
                    location=item.location,
                    skills=tuple(item.skills),
                    salary_min=item.salary_min,
                    salary_max=item.salary_max,
                    currency=item.currency,
                    english_level=item.english_level,
                    about_me=item.about_me,
                    match_score=item.match_score,
                    explanation=item.explanation,
                ),
                is_consumed=False,
            )
            for index, item in enumerate(batch.items)
        ]

        await uow.searches.replace_pool(session.id, pool_items)
        session.search_offset += len(pool_items)
        session.search_total = max(session.search_total, batch.total)
        await uow.searches.save(session)
        await uow.flush()

        return self._RefillResult(
            pool_item=await uow.searches.get_next_pool_candidate(session.id),
            is_degraded=batch.is_degraded,
        )

    @staticmethod
    def _enrich_candidate(
        candidate: CandidateShortProfile,
        snapshot: SearchCandidateSnapshot,
    ) -> CandidateShortProfile:
        return CandidateShortProfile(
            id=candidate.id,
            display_name=candidate.display_name,
            headline_role=candidate.headline_role,
            location=candidate.location,
            work_modes=list(candidate.work_modes),
            experience_years=candidate.experience_years,
            contacts_visibility=candidate.contacts_visibility,
            contacts=candidate.contacts,
            can_view_contacts=candidate.can_view_contacts,
            status=candidate.status,
            english_level=candidate.english_level,
            about_me=candidate.about_me,
            salary_min=candidate.salary_min,
            salary_max=candidate.salary_max,
            currency=candidate.currency,
            skills=list(candidate.skills),
            education=list(candidate.education),
            experiences=list(candidate.experiences),
            projects=list(candidate.projects),
            avatar_file_id=candidate.avatar_file_id,
            avatar_download_url=candidate.avatar_download_url,
            resume_file_id=candidate.resume_file_id,
            resume_download_url=candidate.resume_download_url,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
            version_id=candidate.version_id,
            explanation=snapshot.explanation,
            match_score=snapshot.match_score,
        )
