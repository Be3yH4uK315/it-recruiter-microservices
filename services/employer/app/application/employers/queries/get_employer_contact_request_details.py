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
from app.domain.employer.errors import (
    ContactRequestForbiddenError,
    ContactRequestNotFoundError,
    EmployerNotFoundError,
)


@dataclass(slots=True, frozen=True)
class EmployerContactRequestDetails:
    id: UUID
    employer_id: UUID
    candidate_id: UUID
    candidate_name: str
    status: ContactRequestStatusView
    granted: bool
    created_at: str
    responded_at: str | None = None


class GetEmployerContactRequestDetailsHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        candidate_gateway: CandidateGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._candidate_gateway = candidate_gateway

    async def __call__(
        self,
        *,
        employer_id: UUID,
        employer_telegram_id: int,
        request_id: UUID,
    ) -> EmployerContactRequestDetails:
        async with self._uow_factory() as uow:
            employer = await uow.employers.get_by_id(employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {employer_id} not found")

            if employer.telegram_id != employer_telegram_id:
                raise ContactRequestForbiddenError(
                    "employer is not allowed to access this contact request"
                )

            request = await uow.contact_requests.get_by_id(request_id)
            if request is None:
                raise ContactRequestNotFoundError(f"contact request {request_id} not found")

            if request.employer_id != employer_id:
                raise ContactRequestForbiddenError(
                    "employer is not allowed to access this contact request"
                )

            candidate = await self._candidate_gateway.get_candidate_profile(
                candidate_id=request.candidate_id,
                employer_telegram_id=employer.telegram_id,
            )

            return EmployerContactRequestDetails(
                id=request.id,
                employer_id=request.employer_id,
                candidate_id=request.candidate_id,
                candidate_name=candidate.display_name if candidate else "Кандидат",
                status=map_contact_request_status_to_view(request.status),
                granted=request.granted,
                created_at=request.created_at.isoformat(),
                responded_at=request.responded_at.isoformat() if request.responded_at else None,
            )
