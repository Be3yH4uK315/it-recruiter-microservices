from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import CandidateGateway
from app.application.common.uow import UnitOfWork
from app.application.employers.dto.views import (
    ContactRequestStatusView,
    map_contact_request_status_to_view,
)
from app.domain.employer.errors import ContactRequestNotFoundError, EmployerNotFoundError


@dataclass(slots=True, frozen=True)
class ContactRequestDetails:
    id: UUID
    employer_telegram_id: int
    candidate_id: UUID
    candidate_name: str
    status: ContactRequestStatusView
    granted: bool


class GetContactRequestDetailsHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        candidate_gateway: CandidateGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._candidate_gateway = candidate_gateway

    async def __call__(self, request_id: UUID) -> ContactRequestDetails:
        async with self._uow_factory() as uow:
            request = await uow.contact_requests.get_by_id(request_id)
            if request is None:
                raise ContactRequestNotFoundError(f"contact request {request_id} not found")

            employer = await uow.employers.get_by_id(request.employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {request.employer_id} not found")

            candidate = await self._candidate_gateway.get_candidate_profile(
                candidate_id=request.candidate_id,
                employer_telegram_id=employer.telegram_id,
            )

            return ContactRequestDetails(
                id=request.id,
                employer_telegram_id=employer.telegram_id,
                candidate_id=request.candidate_id,
                candidate_name=candidate.display_name if candidate is not None else "Кандидат",
                status=map_contact_request_status_to_view(request.status),
                granted=request.granted,
            )
