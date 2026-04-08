from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

from app.application.common.contracts import CandidateGateway, CandidateShortProfile
from app.application.common.uow import UnitOfWork
from app.domain.employer.errors import EmployerNotFoundError


class GetFavoritesHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        candidate_gateway: CandidateGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._candidate_gateway = candidate_gateway

    async def __call__(self, employer_id: UUID) -> list[CandidateShortProfile]:
        async with self._uow_factory() as uow:
            employer = await uow.employers.get_by_id(employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {employer_id} not found")

            candidate_ids = await uow.searches.list_favorite_candidate_ids(employer_id)
            if not candidate_ids:
                return []

            tasks = [
                self._candidate_gateway.get_candidate_profile(
                    candidate_id=candidate_id,
                    employer_telegram_id=employer.telegram_id,
                )
                for candidate_id in candidate_ids
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        return [item for item in results if isinstance(item, CandidateShortProfile)]
