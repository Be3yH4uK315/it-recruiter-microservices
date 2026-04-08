from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.application.common.contracts import CandidateGateway
from app.application.common.event_dispatch import dispatch_contact_request_events
from app.application.common.uow import UnitOfWork
from app.application.employers.dto.views import ContactRequestStatusView
from app.domain.employer.entities import ContactRequest
from app.domain.employer.enums import ContactRequestStatus
from app.domain.employer.errors import EmployerNotFoundError


@dataclass(slots=True, frozen=True)
class RequestContactAccessCommand:
    employer_id: UUID
    candidate_id: UUID


@dataclass(slots=True, frozen=True)
class RequestContactAccessResult:
    granted: bool
    status: ContactRequestStatusView
    contacts: dict[str, str | None] | None = None
    notification_info: dict[str, str | int | None] | None = None
    request_id: UUID | None = None


class RequestContactAccessHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        candidate_gateway: CandidateGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._candidate_gateway = candidate_gateway

    async def __call__(self, command: RequestContactAccessCommand) -> RequestContactAccessResult:
        async with self._uow_factory() as uow:
            employer = await uow.employers.get_by_id(command.employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {command.employer_id} not found")

            existing = await uow.contact_requests.get_by_employer_and_candidate(
                employer_id=command.employer_id,
                candidate_id=command.candidate_id,
            )

            profile = await self._candidate_gateway.get_candidate_profile(
                candidate_id=command.candidate_id,
                employer_telegram_id=employer.telegram_id,
            )
            if profile is None:
                return RequestContactAccessResult(
                    granted=False,
                    status=ContactRequestStatusView.NOT_FOUND,
                    contacts=None,
                    notification_info=None,
                    request_id=existing.id if existing else None,
                )

            visibility = (profile.contacts_visibility or "on_request").strip().lower()

            if visibility == "public":
                if existing is None:
                    request = ContactRequest.create(
                        id=uuid4(),
                        employer_id=command.employer_id,
                        candidate_id=command.candidate_id,
                        status=ContactRequestStatus.GRANTED,
                    )
                    await uow.contact_requests.add(request)
                else:
                    request = existing
                    if request.status != ContactRequestStatus.GRANTED:
                        request.approve()
                        await uow.contact_requests.save(request)

                await dispatch_contact_request_events(
                    uow=uow,
                    employer=employer,
                    contact_request=request,
                )
                await uow.flush()

                return RequestContactAccessResult(
                    granted=True,
                    status=ContactRequestStatusView.GRANTED,
                    contacts=profile.contacts,
                    notification_info=None,
                    request_id=request.id,
                )

            if visibility == "hidden":
                if existing is None:
                    request = ContactRequest.create(
                        id=uuid4(),
                        employer_id=command.employer_id,
                        candidate_id=command.candidate_id,
                        status=ContactRequestStatus.REJECTED,
                    )
                    await uow.contact_requests.add(request)
                else:
                    request = existing
                    if request.status != ContactRequestStatus.REJECTED:
                        request.reject()
                        await uow.contact_requests.save(request)

                await dispatch_contact_request_events(
                    uow=uow,
                    employer=employer,
                    contact_request=request,
                )
                await uow.flush()

                return RequestContactAccessResult(
                    granted=False,
                    status=ContactRequestStatusView.REJECTED,
                    contacts=None,
                    notification_info=None,
                    request_id=request.id,
                )

            if existing is None:
                request = ContactRequest.create(
                    id=uuid4(),
                    employer_id=command.employer_id,
                    candidate_id=command.candidate_id,
                    status=ContactRequestStatus.PENDING,
                )
                await uow.contact_requests.add(request)
                await dispatch_contact_request_events(
                    uow=uow,
                    employer=employer,
                    contact_request=request,
                )
                await uow.flush()

                return RequestContactAccessResult(
                    granted=False,
                    status=ContactRequestStatusView.PENDING,
                    contacts=None,
                    notification_info={
                        "employer_company": employer.company or "Неизвестная компания",
                        "candidate_id": str(profile.id),
                        "request_id": str(request.id),
                    },
                    request_id=request.id,
                )

            if existing.status == ContactRequestStatus.GRANTED:
                return RequestContactAccessResult(
                    granted=True,
                    status=ContactRequestStatusView.GRANTED,
                    contacts=profile.contacts,
                    notification_info=None,
                    request_id=existing.id,
                )

            if existing.status == ContactRequestStatus.PENDING:
                return RequestContactAccessResult(
                    granted=False,
                    status=ContactRequestStatusView.PENDING,
                    contacts=None,
                    notification_info={
                        "employer_company": employer.company or "Неизвестная компания",
                        "candidate_id": str(profile.id),
                        "request_id": str(existing.id),
                    },
                    request_id=existing.id,
                )

            existing.reopen_pending()
            await uow.contact_requests.save(existing)
            await dispatch_contact_request_events(
                uow=uow,
                employer=employer,
                contact_request=existing,
            )
            await uow.flush()

            return RequestContactAccessResult(
                granted=False,
                status=ContactRequestStatusView.PENDING,
                contacts=None,
                notification_info={
                    "employer_company": employer.company or "Неизвестная компания",
                    "candidate_id": str(profile.id),
                    "request_id": str(existing.id),
                },
                request_id=existing.id,
            )
