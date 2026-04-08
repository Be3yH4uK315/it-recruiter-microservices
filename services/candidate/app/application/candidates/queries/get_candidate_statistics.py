from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import EmployerGateway
from app.application.common.uow import UnitOfWork
from app.domain.candidate.errors import CandidateNotFoundError


@dataclass(slots=True, frozen=True)
class CandidateStatisticsResult:
    total_views: int
    total_likes: int
    total_contact_requests: int
    is_degraded: bool = False


class GetCandidateStatisticsHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        employer_gateway: EmployerGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._employer_gateway = employer_gateway

    async def __call__(self, candidate_id: UUID) -> CandidateStatisticsResult:
        async with self._uow_factory() as uow:
            candidate = await uow.candidates.get_by_id(candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate {candidate_id} not found")

        raw_stats = await self._employer_gateway.get_candidate_statistics(
            candidate_id=candidate_id,
        )

        return CandidateStatisticsResult(
            total_views=int(raw_stats.get("total_views", 0)),
            total_likes=int(raw_stats.get("total_likes", 0)),
            total_contact_requests=int(raw_stats.get("total_contact_requests", 0)),
            is_degraded=bool(raw_stats.get("is_degraded", False)),
        )
