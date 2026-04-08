from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.application.common.contracts import EventMapper
from app.domain.common.events import DomainEvent
from app.domain.employer.entities import (
    ContactRequest,
    ContactRequestCreated,
    ContactRequestGranted,
    ContactRequestRejected,
    EmployerAvatarDeleted,
    EmployerAvatarReplaced,
    EmployerDocumentDeleted,
    EmployerDocumentReplaced,
    EmployerProfile,
    EmployerProfileUpdated,
    EmployerRegistered,
    SearchSession,
    SearchSessionClosed,
    SearchSessionCreated,
    SearchSessionPaused,
    SearchSessionResumed,
)


class DefaultEventMapper(EventMapper):
    def map_domain_event(
        self,
        *,
        event: DomainEvent,
        employer: EmployerProfile | None = None,
        search_session: SearchSession | None = None,
        contact_request: ContactRequest | None = None,
    ) -> list[tuple[str, dict]]:
        messages: list[tuple[str, dict]] = []

        base_payload = {
            "event_id": self._serialize_uuid(event.event_id),
            "occurred_at": self._serialize_dt(event.occurred_at),
            "event_name": event.event_name,
        }

        if isinstance(event, EmployerRegistered):
            if employer is None:
                raise ValueError("employer is required for EmployerRegistered event")

            messages.append(
                (
                    "employer.created",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "telegram_id": employer.telegram_id,
                        "snapshot": self._build_employer_snapshot(employer),
                    },
                )
            )
            return messages

        if isinstance(event, EmployerProfileUpdated):
            if employer is None:
                raise ValueError("employer is required for EmployerProfileUpdated event")

            messages.append(
                (
                    "employer.updated",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "snapshot": self._build_employer_snapshot(employer),
                    },
                )
            )
            return messages

        if isinstance(event, EmployerAvatarReplaced):
            if employer is None:
                raise ValueError("employer is required for EmployerAvatarReplaced event")

            messages.append(
                (
                    "employer.avatar.replaced",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "new_file_id": self._serialize_uuid(event.new_file_id),
                        "old_file_id": self._serialize_uuid(event.old_file_id),
                    },
                )
            )
            return messages

        if isinstance(event, EmployerAvatarDeleted):
            if employer is None:
                raise ValueError("employer is required for EmployerAvatarDeleted event")

            messages.append(
                (
                    "employer.avatar.deleted",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "file_id": self._serialize_uuid(event.file_id),
                    },
                )
            )
            return messages

        if isinstance(event, EmployerDocumentReplaced):
            if employer is None:
                raise ValueError("employer is required for EmployerDocumentReplaced event")

            messages.append(
                (
                    "employer.document.replaced",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "new_file_id": self._serialize_uuid(event.new_file_id),
                        "old_file_id": self._serialize_uuid(event.old_file_id),
                    },
                )
            )
            return messages

        if isinstance(event, EmployerDocumentDeleted):
            if employer is None:
                raise ValueError("employer is required for EmployerDocumentDeleted event")

            messages.append(
                (
                    "employer.document.deleted",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "file_id": self._serialize_uuid(event.file_id),
                    },
                )
            )
            return messages

        if isinstance(event, SearchSessionCreated):
            if employer is None or search_session is None:
                raise ValueError(
                    "employer and search_session are required for SearchSessionCreated event"
                )

            messages.append(
                (
                    "employer.search.created",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "session_id": self._serialize_uuid(search_session.id),
                        "search_title": search_session.title,
                        "status": search_session.status.value,
                        "filters": search_session.filters.to_primitives(),
                        "search_offset": search_session.search_offset,
                        "search_total": search_session.search_total,
                    },
                )
            )
            return messages

        if isinstance(event, SearchSessionPaused):
            if employer is None or search_session is None:
                raise ValueError(
                    "employer and search_session are required for SearchSessionPaused event"
                )

            messages.append(
                (
                    "employer.search.paused",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "session_id": self._serialize_uuid(search_session.id),
                        "status": search_session.status.value,
                    },
                )
            )
            return messages

        if isinstance(event, SearchSessionResumed):
            if employer is None or search_session is None:
                raise ValueError(
                    "employer and search_session are required for SearchSessionResumed event"
                )

            messages.append(
                (
                    "employer.search.resumed",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "session_id": self._serialize_uuid(search_session.id),
                        "status": search_session.status.value,
                    },
                )
            )
            return messages

        if isinstance(event, SearchSessionClosed):
            if employer is None or search_session is None:
                raise ValueError(
                    "employer and search_session are required for SearchSessionClosed event"
                )

            messages.append(
                (
                    "employer.search.closed",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "session_id": self._serialize_uuid(search_session.id),
                        "status": search_session.status.value,
                    },
                )
            )
            return messages

        if isinstance(event, ContactRequestCreated):
            if employer is None or contact_request is None:
                raise ValueError(
                    "employer and contact_request are required for ContactRequestCreated event"
                )

            messages.append(
                (
                    "employer.contact.requested",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "request_id": self._serialize_uuid(contact_request.id),
                        "candidate_id": self._serialize_uuid(contact_request.candidate_id),
                        "status": contact_request.status.value,
                        "granted": contact_request.granted,
                        "created_at": self._serialize_dt(contact_request.created_at),
                        "responded_at": (
                            self._serialize_dt(contact_request.responded_at)
                            if contact_request.responded_at is not None
                            else None
                        ),
                    },
                )
            )
            return messages

        if isinstance(event, ContactRequestGranted):
            if employer is None or contact_request is None:
                raise ValueError(
                    "employer and contact_request are required for ContactRequestGranted event"
                )

            messages.append(
                (
                    "employer.contact.granted",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "request_id": self._serialize_uuid(contact_request.id),
                        "candidate_id": self._serialize_uuid(contact_request.candidate_id),
                        "status": contact_request.status.value,
                        "granted": True,
                        "created_at": self._serialize_dt(contact_request.created_at),
                        "responded_at": (
                            self._serialize_dt(contact_request.responded_at)
                            if contact_request.responded_at is not None
                            else None
                        ),
                    },
                )
            )
            return messages

        if isinstance(event, ContactRequestRejected):
            if employer is None or contact_request is None:
                raise ValueError(
                    "employer and contact_request are required for ContactRequestRejected event"
                )

            messages.append(
                (
                    "employer.contact.rejected",
                    {
                        **base_payload,
                        "employer_id": self._serialize_uuid(employer.id),
                        "request_id": self._serialize_uuid(contact_request.id),
                        "candidate_id": self._serialize_uuid(contact_request.candidate_id),
                        "status": contact_request.status.value,
                        "granted": False,
                        "created_at": self._serialize_dt(contact_request.created_at),
                        "responded_at": (
                            self._serialize_dt(contact_request.responded_at)
                            if contact_request.responded_at is not None
                            else None
                        ),
                    },
                )
            )
            return messages

        return messages

    def _build_employer_snapshot(self, employer: EmployerProfile) -> dict:
        return {
            "id": self._serialize_uuid(employer.id),
            "telegram_id": employer.telegram_id,
            "company": employer.company,
            "contacts": employer.contacts.to_dict() if employer.contacts else None,
            "avatar_file_id": self._serialize_uuid(employer.avatar_file_id),
            "document_file_id": self._serialize_uuid(employer.document_file_id),
            "created_at": self._serialize_dt(employer.created_at) if employer.created_at else None,
            "updated_at": self._serialize_dt(employer.updated_at) if employer.updated_at else None,
        }

    @staticmethod
    def _serialize_uuid(value: UUID | None) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _serialize_dt(value: datetime) -> str:
        return value.isoformat()
