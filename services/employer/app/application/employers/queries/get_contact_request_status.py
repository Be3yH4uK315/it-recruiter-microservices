from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.uow import UnitOfWork
from app.application.employers.dto.views import (
    ContactRequestStatusView,
    map_contact_request_status_to_view,
)


@dataclass(slots=True, frozen=True)
class ContactRequestStatusResult:
    exists: bool
    status: ContactRequestStatusView
    granted: bool
    request_id: UUID | None = None


class GetContactRequestStatusHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(
        self,
        *,
        employer_id: UUID,
        candidate_id: UUID,
    ) -> ContactRequestStatusResult:
        async with self._uow_factory() as uow:
            request = await uow.contact_requests.get_by_employer_and_candidate(
                employer_id=employer_id,
                candidate_id=candidate_id,
            )
            if request is None:
                return ContactRequestStatusResult(
                    exists=False,
                    status=ContactRequestStatusView.NOT_FOUND,
                    granted=False,
                    request_id=None,
                )

            return ContactRequestStatusResult(
                exists=True,
                status=map_contact_request_status_to_view(request.status),
                granted=request.granted,
                request_id=request.id,
            )
