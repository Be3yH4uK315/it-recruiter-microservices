from __future__ import annotations

from uuid import uuid4

from app.domain.employer.entities import EmployerProfile, SearchSession
from app.domain.employer.enums import SearchStatus
from app.domain.employer.value_objects import EmployerContacts, SearchFilters


def test_create_employer_emits_registered_event() -> None:
    employer = EmployerProfile.create(
        id=uuid4(),
        telegram_id=1001,
        company="Acme",
        contacts=EmployerContacts(email="hr@acme.test"),
    )

    events = employer.pull_events()
    assert len(events) == 1
    assert events[0].event_name == "employer_registered"


def test_update_employer_updates_fields() -> None:
    employer = EmployerProfile.create(
        id=uuid4(),
        telegram_id=1001,
        company="Acme",
    )
    employer.pull_events()

    employer.update_profile(
        company="Acme Updated",
        contacts=EmployerContacts(email="new@acme.test"),
    )

    assert employer.company == "Acme Updated"
    assert employer.contacts is not None
    assert employer.contacts.email == "new@acme.test"


def test_create_search_session_emits_event() -> None:
    session = SearchSession.create(
        id=uuid4(),
        employer_id=uuid4(),
        title="Senior Python",
        filters=SearchFilters(role="Python Developer"),
    )

    assert session.status == SearchStatus.ACTIVE
    events = session.pull_events()
    assert len(events) == 1
    assert events[0].event_name == "search_session_created"
