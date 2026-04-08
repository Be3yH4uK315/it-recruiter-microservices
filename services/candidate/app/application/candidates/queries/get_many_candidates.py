from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.application.common.uow import UnitOfWork
from app.domain.candidate.entities import CandidateProfile


class GetManyCandidatesHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, candidate_ids: list[UUID]) -> list[CandidateProfile]:
        async with self._uow_factory() as uow:
            return await uow.candidates.get_many_by_ids(candidate_ids)
