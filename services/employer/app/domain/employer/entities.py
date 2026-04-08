from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Final
from uuid import UUID

from app.domain.common.events import DomainEvent
from app.domain.employer.enums import (
    ContactRequestStatus,
    DecisionType,
    SearchStatus,
)
from app.domain.employer.errors import (
    ContactRequestAlreadyResolvedError,
    DuplicateDecisionError,
    EmployerDomainError,
    InvalidSearchFilterError,
    SearchSessionClosedError,
    SearchSessionPausedError,
)
from app.domain.employer.value_objects import (
    EmployerContacts,
    SearchFilters,
    SearchSessionCandidate,
)

UNSET: Final = object()


@dataclass(slots=True, frozen=True)
class EmployerRegistered(DomainEvent):
    employer_id: UUID | None = None
    telegram_id: int | None = None


@dataclass(slots=True, frozen=True)
class EmployerProfileUpdated(DomainEvent):
    employer_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class EmployerAvatarReplaced(DomainEvent):
    employer_id: UUID | None = None
    new_file_id: UUID | None = None
    old_file_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class EmployerAvatarDeleted(DomainEvent):
    employer_id: UUID | None = None
    file_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class EmployerDocumentReplaced(DomainEvent):
    employer_id: UUID | None = None
    new_file_id: UUID | None = None
    old_file_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class EmployerDocumentDeleted(DomainEvent):
    employer_id: UUID | None = None
    file_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class SearchSessionCreated(DomainEvent):
    session_id: UUID | None = None
    employer_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class SearchSessionPaused(DomainEvent):
    session_id: UUID | None = None
    employer_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class SearchSessionResumed(DomainEvent):
    session_id: UUID | None = None
    employer_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class SearchSessionClosed(DomainEvent):
    session_id: UUID | None = None
    employer_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class ContactRequestCreated(DomainEvent):
    request_id: UUID | None = None
    employer_id: UUID | None = None
    candidate_id: UUID | None = None
    status: str = ContactRequestStatus.PENDING.value


@dataclass(slots=True, frozen=True)
class ContactRequestGranted(DomainEvent):
    request_id: UUID | None = None
    employer_id: UUID | None = None
    candidate_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class ContactRequestRejected(DomainEvent):
    request_id: UUID | None = None
    employer_id: UUID | None = None
    candidate_id: UUID | None = None


@dataclass(slots=True)
class EmployerProfile:
    id: UUID
    telegram_id: int
    company: str | None = None
    contacts: EmployerContacts | None = None
    avatar_file_id: UUID | None = None
    document_file_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        telegram_id: int,
        company: str | None = None,
        contacts: EmployerContacts | None = None,
        avatar_file_id: UUID | None = None,
        document_file_id: UUID | None = None,
    ) -> "EmployerProfile":
        if telegram_id <= 0:
            raise EmployerDomainError("telegram_id must be positive")

        employer = cls(
            id=id,
            telegram_id=telegram_id,
            company=cls._normalize_optional_text(company),
            contacts=contacts,
            avatar_file_id=avatar_file_id,
            document_file_id=document_file_id,
        )
        employer._events.append(
            EmployerRegistered(
                employer_id=employer.id,
                telegram_id=employer.telegram_id,
            )
        )
        return employer

    def update_profile(
        self,
        *,
        company: str | None | object = UNSET,
        contacts: EmployerContacts | None | object = UNSET,
    ) -> None:
        changed = False

        if company is not UNSET:
            normalized_company = self._normalize_optional_text(company)
            if normalized_company != self.company:
                self.company = normalized_company
                changed = True

        if contacts is not UNSET and contacts != self.contacts:
            self.contacts = contacts
            changed = True

        if changed:
            self.updated_at = datetime.now(timezone.utc)
            self._events.append(
                EmployerProfileUpdated(
                    employer_id=self.id,
                )
            )

    def replace_avatar(self, *, file_id: UUID) -> UUID | None:
        old_file_id = self.avatar_file_id
        self.avatar_file_id = file_id
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            EmployerAvatarReplaced(
                employer_id=self.id,
                new_file_id=file_id,
                old_file_id=old_file_id,
            )
        )
        return old_file_id

    def delete_avatar(self) -> UUID | None:
        if self.avatar_file_id is None:
            return None

        old_file_id = self.avatar_file_id
        self.avatar_file_id = None
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            EmployerAvatarDeleted(
                employer_id=self.id,
                file_id=old_file_id,
            )
        )
        return old_file_id

    def replace_document(self, *, file_id: UUID) -> UUID | None:
        old_file_id = self.document_file_id
        self.document_file_id = file_id
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            EmployerDocumentReplaced(
                employer_id=self.id,
                new_file_id=file_id,
                old_file_id=old_file_id,
            )
        )
        return old_file_id

    def delete_document(self) -> UUID | None:
        if self.document_file_id is None:
            return None

        old_file_id = self.document_file_id
        self.document_file_id = None
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            EmployerDocumentDeleted(
                employer_id=self.id,
                file_id=old_file_id,
            )
        )
        return old_file_id

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


@dataclass(slots=True)
class SearchDecision:
    candidate_id: UUID
    decision: DecisionType
    note: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class SearchSession:
    id: UUID
    employer_id: UUID
    title: str
    filters: SearchFilters
    status: SearchStatus = SearchStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decisions: dict[UUID, SearchDecision] = field(default_factory=dict)
    candidate_pool: list[SearchSessionCandidate] = field(default_factory=list)
    search_offset: int = 0
    search_total: int = 0
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        employer_id: UUID,
        title: str,
        filters: SearchFilters,
    ) -> "SearchSession":
        normalized_title = title.strip()
        if len(normalized_title) < 3:
            raise InvalidSearchFilterError("search title must contain at least 3 characters")

        session = cls(
            id=id,
            employer_id=employer_id,
            title=normalized_title,
            filters=filters,
            status=SearchStatus.ACTIVE,
        )
        session._events.append(
            SearchSessionCreated(
                session_id=session.id,
                employer_id=session.employer_id,
            )
        )
        return session

    def submit_decision(
        self,
        *,
        candidate_id: UUID,
        decision: DecisionType,
        note: str | None = None,
    ) -> SearchDecision:
        if self.status == SearchStatus.CLOSED:
            raise SearchSessionClosedError("search session is closed")
        if self.status == SearchStatus.PAUSED:
            raise SearchSessionPausedError("search session is paused")
        if candidate_id in self.decisions:
            raise DuplicateDecisionError("decision for candidate already exists")

        item = SearchDecision(
            candidate_id=candidate_id,
            decision=decision,
            note=note.strip() if note else None,
        )
        self.decisions[candidate_id] = item
        self.updated_at = datetime.now(timezone.utc)
        return item

    def viewed_candidate_ids(self) -> list[UUID]:
        return list(self.decisions.keys())

    def has_more_remote_candidates(self) -> bool:
        return self.search_offset < self.search_total

    def is_active(self) -> bool:
        return self.status == SearchStatus.ACTIVE

    def is_paused(self) -> bool:
        return self.status == SearchStatus.PAUSED

    def is_closed(self) -> bool:
        return self.status == SearchStatus.CLOSED

    def pause(self) -> None:
        if self.status == SearchStatus.CLOSED:
            raise SearchSessionClosedError("search session is closed")
        if self.status == SearchStatus.PAUSED:
            return

        self.status = SearchStatus.PAUSED
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            SearchSessionPaused(
                session_id=self.id,
                employer_id=self.employer_id,
            )
        )

    def activate(self) -> None:
        if self.status == SearchStatus.CLOSED:
            raise SearchSessionClosedError("search session is closed")
        if self.status == SearchStatus.ACTIVE:
            return

        self.status = SearchStatus.ACTIVE
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            SearchSessionResumed(
                session_id=self.id,
                employer_id=self.employer_id,
            )
        )

    def close(self) -> None:
        if self.status == SearchStatus.CLOSED:
            return

        self.status = SearchStatus.CLOSED
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            SearchSessionClosed(
                session_id=self.id,
                employer_id=self.employer_id,
            )
        )

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events


@dataclass(slots=True)
class ContactRequest:
    id: UUID
    employer_id: UUID
    candidate_id: UUID
    status: ContactRequestStatus = ContactRequestStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    responded_at: datetime | None = None
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        employer_id: UUID,
        candidate_id: UUID,
        status: ContactRequestStatus,
    ) -> "ContactRequest":
        now = datetime.now(timezone.utc)
        responded_at = (
            now if status in {ContactRequestStatus.GRANTED, ContactRequestStatus.REJECTED} else None
        )

        request = cls(
            id=id,
            employer_id=employer_id,
            candidate_id=candidate_id,
            status=status,
            created_at=now,
            responded_at=responded_at,
        )
        request._events.append(
            ContactRequestCreated(
                request_id=request.id,
                employer_id=request.employer_id,
                candidate_id=request.candidate_id,
                status=request.status.value,
            )
        )
        return request

    @property
    def granted(self) -> bool:
        return self.status == ContactRequestStatus.GRANTED

    def is_pending(self) -> bool:
        return self.status == ContactRequestStatus.PENDING

    def is_resolved(self) -> bool:
        return self.status in {ContactRequestStatus.GRANTED, ContactRequestStatus.REJECTED}

    def approve(self) -> None:
        if self.status == ContactRequestStatus.GRANTED:
            return
        self.status = ContactRequestStatus.GRANTED
        self.responded_at = datetime.now(timezone.utc)
        self._events.append(
            ContactRequestGranted(
                request_id=self.id,
                employer_id=self.employer_id,
                candidate_id=self.candidate_id,
            )
        )

    def reject(self) -> None:
        if self.status == ContactRequestStatus.REJECTED:
            return
        self.status = ContactRequestStatus.REJECTED
        self.responded_at = datetime.now(timezone.utc)
        self._events.append(
            ContactRequestRejected(
                request_id=self.id,
                employer_id=self.employer_id,
                candidate_id=self.candidate_id,
            )
        )

    def reopen_pending(self) -> None:
        if self.status == ContactRequestStatus.PENDING:
            return
        self.status = ContactRequestStatus.PENDING
        self.responded_at = None
        self._events.append(
            ContactRequestCreated(
                request_id=self.id,
                employer_id=self.employer_id,
                candidate_id=self.candidate_id,
                status=self.status.value,
            )
        )

    def ensure_not_resolved(self) -> None:
        if self.is_resolved():
            raise ContactRequestAlreadyResolvedError("contact request is already resolved")

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events
