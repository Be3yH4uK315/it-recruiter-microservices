from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.application.common.uow import UnitOfWork
from app.domain.employer.errors import EmployerNotFoundError


class GetEmployerStatisticsHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, employer_id: UUID) -> dict[str, int]:
        async with self._uow_factory() as uow:
            employer = await uow.employers.get_by_id(employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {employer_id} not found")

            return await uow.searches.get_employer_statistics(employer_id)
