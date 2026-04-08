from __future__ import annotations

from app.application.common.uow import UnitOfWork
from app.domain.auth.entities import RefreshSession, User


async def dispatch_user_events(
    *,
    uow: UnitOfWork,
    user: User,
) -> None:
    for event in user.pull_events():
        mapped_messages = uow.event_mapper.map_domain_event(
            event=event,
            user=user,
        )

        for routing_key, payload in mapped_messages:
            await uow.outbox.publish(
                routing_key=routing_key,
                payload=payload,
            )


async def dispatch_refresh_session_events(
    *,
    uow: UnitOfWork,
    user: User,
    refresh_session: RefreshSession,
) -> None:
    for event in refresh_session.pull_events():
        mapped_messages = uow.event_mapper.map_domain_event(
            event=event,
            user=user,
            refresh_session=refresh_session,
        )

        for routing_key, payload in mapped_messages:
            await uow.outbox.publish(
                routing_key=routing_key,
                payload=payload,
            )
