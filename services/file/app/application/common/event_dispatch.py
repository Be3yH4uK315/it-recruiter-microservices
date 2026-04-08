from __future__ import annotations

from app.application.common.uow import UnitOfWork
from app.domain.file.entities import StoredFile


async def dispatch_file_events(
    *,
    uow: UnitOfWork,
    file: StoredFile,
) -> None:
    for event in file.pull_events():
        mapped_messages = uow.event_mapper.map_domain_event(event=event)

        for routing_key, payload in mapped_messages:
            await uow.outbox.publish(
                routing_key=routing_key,
                payload=payload,
            )
