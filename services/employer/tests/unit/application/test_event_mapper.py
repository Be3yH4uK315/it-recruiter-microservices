from __future__ import annotations

from uuid import uuid4

from app.domain.employer.entities import ContactRequest, EmployerProfile
from app.domain.employer.enums import ContactRequestStatus
from app.domain.employer.value_objects import EmployerContacts
from app.infrastructure.messaging.event_mapper import DefaultEventMapper


def test_maps_employer_registered_event() -> None:
    employer = EmployerProfile.create(
        id=uuid4(),
        telegram_id=1001,
        company="Acme",
        contacts=EmployerContacts(email="hr@acme.test"),
    )
    event = employer.pull_events()[0]

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(event=event, employer=employer)

    assert len(messages) == 1
    routing_key, payload = messages[0]
    assert routing_key == "employer.created"
    assert payload["event_name"] == "employer_registered"
    assert payload["snapshot"]["company"] == "Acme"


def test_maps_contact_request_created_event() -> None:
    employer = EmployerProfile.create(
        id=uuid4(),
        telegram_id=1001,
        company="Acme",
    )
    employer.pull_events()

    request = ContactRequest.create(
        id=uuid4(),
        employer_id=employer.id,
        candidate_id=uuid4(),
        status=ContactRequestStatus.PENDING,
    )
    event = request.pull_events()[0]

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(
        event=event,
        employer=employer,
        contact_request=request,
    )

    assert len(messages) == 1
    routing_key, payload = messages[0]
    assert routing_key == "employer.contact.requested"
    assert payload["granted"] is False
