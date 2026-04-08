from __future__ import annotations

from app.application.common.uow import UnitOfWork
from app.domain.candidate.entities import CandidateProfile


async def dispatch_candidate_events(
    *,
    uow: UnitOfWork,
    candidate: CandidateProfile,
) -> None:
    for event in candidate.pull_events():
        mapped_messages = uow.event_mapper.map_domain_event(
            event=event,
            candidate=candidate,
        )

        for routing_key, payload in mapped_messages:
            await uow.outbox.publish(
                routing_key=routing_key,
                payload=payload,
            )
