from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.application.common.uow import UnitOfWork
from app.domain.candidate.entities import CandidateProfile
from app.domain.candidate.errors import CandidateNotFoundError


class GetCandidateHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, candidate_id: UUID) -> CandidateProfile:
        async with self._uow_factory() as uow:
            candidate = await uow.candidates.get_by_id(candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate {candidate_id} not found")

            return candidate
