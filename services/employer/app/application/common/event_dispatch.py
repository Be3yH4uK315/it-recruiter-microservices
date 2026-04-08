from __future__ import annotations

from app.application.common.uow import UnitOfWork
from app.domain.employer.entities import ContactRequest, EmployerProfile, SearchSession


async def dispatch_employer_events(
    *,
    uow: UnitOfWork,
    employer: EmployerProfile,
) -> None:
    for event in employer.pull_events():
        mapped_messages = uow.event_mapper.map_domain_event(
            event=event,
            employer=employer,
        )

        for routing_key, payload in mapped_messages:
            await uow.outbox.publish(
                routing_key=routing_key,
                payload=payload,
            )


async def dispatch_search_session_events(
    *,
    uow: UnitOfWork,
    employer: EmployerProfile,
    search_session: SearchSession,
) -> None:
    for event in search_session.pull_events():
        mapped_messages = uow.event_mapper.map_domain_event(
            event=event,
            employer=employer,
            search_session=search_session,
        )

        for routing_key, payload in mapped_messages:
            await uow.outbox.publish(
                routing_key=routing_key,
                payload=payload,
            )


async def dispatch_contact_request_events(
    *,
    uow: UnitOfWork,
    employer: EmployerProfile,
    contact_request: ContactRequest,
) -> None:
    for event in contact_request.pull_events():
        mapped_messages = uow.event_mapper.map_domain_event(
            event=event,
            employer=employer,
            contact_request=contact_request,
        )

        for routing_key, payload in mapped_messages:
            await uow.outbox.publish(
                routing_key=routing_key,
                payload=payload,
            )
