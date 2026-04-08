from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.event_dispatch import dispatch_contact_request_events
from app.application.common.uow import UnitOfWork
from app.domain.employer.entities import ContactRequest
from app.domain.employer.errors import (
    ContactRequestForbiddenError,
    ContactRequestNotFoundError,
    EmployerNotFoundError,
)


@dataclass(slots=True, frozen=True)
class RespondContactRequestCommand:
    request_id: UUID
    candidate_id: UUID
    granted: bool


class RespondContactRequestHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, command: RespondContactRequestCommand) -> ContactRequest:
        async with self._uow_factory() as uow:
            request = await uow.contact_requests.get_by_id(command.request_id)
            if request is None:
                raise ContactRequestNotFoundError(f"contact request {command.request_id} not found")

            if request.candidate_id != command.candidate_id:
                raise ContactRequestForbiddenError(
                    "candidate is not allowed to respond to this contact request"
                )

            employer = await uow.employers.get_by_id(request.employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {request.employer_id} not found")

            request.ensure_not_resolved()

            if command.granted:
                request.approve()
            else:
                request.reject()

            await uow.contact_requests.save(request)
            await dispatch_contact_request_events(
                uow=uow,
                employer=employer,
                contact_request=request,
            )
            await uow.flush()
            return request
