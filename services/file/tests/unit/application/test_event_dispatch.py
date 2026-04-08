from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.application.common.event_dispatch import dispatch_file_events
from app.domain.file.entities import StoredFile
from app.domain.file.enums import FileCategory


class StubOutbox:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish(self, *, routing_key: str, payload: dict) -> None:
        self.published.append((routing_key, payload))


class StubEventMapper:
    def map_domain_event(self, *, event) -> list[tuple[str, dict]]:
        return [
            (
                event.event_name,
                {
                    "event_name": event.event_name,
                    "event_id": str(event.event_id),
                },
            )
        ]


@dataclass
class StubUow:
    outbox: StubOutbox
    event_mapper: StubEventMapper


@pytest.mark.asyncio
async def test_dispatch_file_events_publishes_all_pending_events() -> None:
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=uuid4(),
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key="candidate-service/candidate_resume/test/resume.pdf",
    )

    uow = StubUow(
        outbox=StubOutbox(),
        event_mapper=StubEventMapper(),
    )

    await dispatch_file_events(
        uow=uow,
        file=file,
    )

    assert len(uow.outbox.published) == 1
    routing_key, payload = uow.outbox.published[0]
    assert routing_key == "file_created"
    assert payload["event_name"] == "file_created"


@pytest.mark.asyncio
async def test_dispatch_file_events_clears_pending_events_after_dispatch() -> None:
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=uuid4(),
        category=FileCategory.CANDIDATE_AVATAR,
        filename="avatar.png",
        content_type="image/png",
        bucket="files",
        object_key="candidate-service/candidate_avatar/test/avatar.png",
    )

    uow = StubUow(
        outbox=StubOutbox(),
        event_mapper=StubEventMapper(),
    )

    await dispatch_file_events(
        uow=uow,
        file=file,
    )

    assert file.pull_events() == []


@pytest.mark.asyncio
async def test_dispatch_file_events_does_nothing_when_no_pending_events() -> None:
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

    uow = StubUow(
        outbox=StubOutbox(),
        event_mapper=StubEventMapper(),
    )

    await dispatch_file_events(
        uow=uow,
        file=file,
    )

    assert uow.outbox.published == []
