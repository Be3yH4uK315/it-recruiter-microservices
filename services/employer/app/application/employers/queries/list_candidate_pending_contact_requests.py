from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.application.common.uow import UnitOfWork
from app.application.employers.dto.views import map_contact_request_status_to_view
from app.domain.employer.enums import ContactRequestStatus


@dataclass(slots=True, frozen=True)
class CandidatePendingContactRequest:
    id: UUID
    employer_id: UUID
    employer_company: str
    employer_telegram_id: int
    status: str
    granted: bool
    created_at: datetime


class ListCandidatePendingContactRequestsHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(
        self,
        *,
        candidate_id: UUID,
        limit: int = 10,
    ) -> list[CandidatePendingContactRequest]:
        async with self._uow_factory() as uow:
            requests = await uow.contact_requests.list_by_candidate(
                candidate_id=candidate_id,
                limit=limit,
            )
            pending_requests = [
                item for item in requests if item.status == ContactRequestStatus.PENDING
            ]
            if not pending_requests:
                return []

            result: list[CandidatePendingContactRequest] = []
            for request in pending_requests:
                employer = await uow.employers.get_by_id(request.employer_id)
                if employer is None:
                    continue
                result.append(
                    CandidatePendingContactRequest(
                        id=request.id,
                        employer_id=request.employer_id,
                        employer_company=employer.company or "Компания",
                        employer_telegram_id=employer.telegram_id,
                        status=map_contact_request_status_to_view(request.status).value,
                        granted=request.granted,
                        created_at=request.created_at,
                    )
                )
            return result
