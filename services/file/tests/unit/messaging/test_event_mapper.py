from __future__ import annotations

from uuid import uuid4

from app.domain.file.entities import StoredFile
from app.domain.file.enums import FileCategory
from app.infrastructure.messaging.event_mapper import DefaultEventMapper


def test_map_file_created_event() -> None:
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=uuid4(),
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key="candidate-service/candidate_resume/test/resume.pdf",
    )
    event = file.pull_events()[0]

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(event=event)

    assert len(messages) == 1
    routing_key, payload = messages[0]

    assert routing_key == "file.created"
    assert payload["event_name"] == "file_created"
    assert payload["file_id"] == str(file.id)
    assert payload["owner_service"] == "candidate-service"
    assert payload["owner_id"] == str(file.owner.owner_id)
    assert payload["category"] == FileCategory.CANDIDATE_RESUME.value
    assert payload["object_key"] == file.object_key
    assert payload["event_id"] is not None
    assert payload["occurred_at"] is not None


def test_map_file_activated_event() -> None:
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=uuid4(),
        category=FileCategory.CANDIDATE_AVATAR,
        filename="avatar.png",
        content_type="image/png",
        bucket="files",
        object_key="candidate-service/candidate_avatar/test/avatar.png",
    )
    file.pull_events()
    file.activate(size_bytes=1024)
    event = file.pull_events()[0]

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(event=event)

    assert len(messages) == 1
    routing_key, payload = messages[0]

    assert routing_key == "file.activated"
    assert payload["event_name"] == "file_activated"
    assert payload["file_id"] == str(file.id)
    assert payload["object_key"] == file.object_key
    assert payload["event_id"] is not None
    assert payload["occurred_at"] is not None


def test_map_file_deleted_event() -> None:
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=uuid4(),
        category=FileCategory.CANDIDATE_AVATAR,
        filename="avatar.png",
        content_type="image/png",
        bucket="files",
        object_key="candidate-service/candidate_avatar/test/avatar.png",
    )
    file.pull_events()
    file.mark_deleted(reason="candidate_avatar_deleted")
    event = file.pull_events()[0]

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(event=event)

    assert len(messages) == 1
    routing_key, payload = messages[0]

    assert routing_key == "file.deleted"
    assert payload["event_name"] == "file_deleted"
    assert payload["file_id"] == str(file.id)
    assert payload["owner_service"] == "candidate-service"
    assert payload["owner_id"] == str(file.owner.owner_id)
    assert payload["category"] == FileCategory.CANDIDATE_AVATAR.value
    assert payload["object_key"] == file.object_key
    assert payload["reason"] == "candidate_avatar_deleted"
    assert payload["event_id"] is not None
    assert payload["occurred_at"] is not None


def test_map_unknown_event_returns_empty_list() -> None:
    from dataclasses import dataclass

    from app.domain.common.events import DomainEvent

    @dataclass(slots=True, kw_only=True, frozen=True)
    class UnknownEvent(DomainEvent):
        event_name: str = "unknown.event"

    mapper = DefaultEventMapper()
    messages = mapper.map_domain_event(event=UnknownEvent())

    assert messages == []
