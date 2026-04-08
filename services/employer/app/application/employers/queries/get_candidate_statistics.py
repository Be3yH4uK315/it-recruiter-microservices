from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.application.common.uow import UnitOfWork


class GetCandidateStatisticsHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, candidate_id: UUID) -> dict[str, int]:
        async with self._uow_factory() as uow:
            return await uow.searches.get_candidate_statistics(candidate_id)
