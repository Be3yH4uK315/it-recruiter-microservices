from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.application.common.contracts import EventMapper
from app.domain.common.events import DomainEvent
from app.domain.file.entities import FileActivated, FileCreated, FileDeleted


class DefaultEventMapper(EventMapper):
    def map_domain_event(
        self,
        *,
        event: DomainEvent,
    ) -> list[tuple[str, dict]]:
        messages: list[tuple[str, dict]] = []

        base_payload = {
            "event_id": self._serialize_uuid(event.event_id),
            "occurred_at": self._serialize_dt(event.occurred_at),
            "event_name": event.event_name,
        }

        if isinstance(event, FileCreated):
            messages.append(
                (
                    "file.created",
                    {
                        **base_payload,
                        "file_id": self._serialize_uuid(event.file_id),
                        "owner_service": event.owner_service,
                        "owner_id": self._serialize_uuid(event.owner_id),
                        "category": event.category,
                        "object_key": event.object_key,
                    },
                )
            )
            return messages

        if isinstance(event, FileActivated):
            messages.append(
                (
                    "file.activated",
                    {
                        **base_payload,
                        "file_id": self._serialize_uuid(event.file_id),
                        "object_key": event.object_key,
                    },
                )
            )
            return messages

        if isinstance(event, FileDeleted):
            messages.append(
                (
                    "file.deleted",
                    {
                        **base_payload,
                        "file_id": self._serialize_uuid(event.file_id),
                        "owner_service": event.owner_service,
                        "owner_id": self._serialize_uuid(event.owner_id),
                        "category": event.category,
                        "object_key": event.object_key,
                        "reason": event.reason,
                    },
                )
            )
            return messages

        return messages

    @staticmethod
    def _serialize_uuid(value: UUID | None) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _serialize_dt(value: datetime) -> str:
        return value.isoformat()
