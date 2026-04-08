from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.application.common.uow import UnitOfWork
from app.domain.employer.enums import ContactRequestStatus


class HasContactAccessHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(
        self,
        *,
        candidate_id: UUID,
        employer_telegram_id: int,
    ) -> bool:
        async with self._uow_factory() as uow:
            employer = await uow.employers.get_by_telegram_id(employer_telegram_id)
            if employer is None:
                return False

            request = await uow.contact_requests.get_by_employer_and_candidate(
                employer_id=employer.id,
                candidate_id=candidate_id,
            )
            if request is None:
                return False

            return request.status == ContactRequestStatus.GRANTED
