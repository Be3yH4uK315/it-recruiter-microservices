from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.file.entities import FileActivated, FileCreated, FileDeleted, StoredFile
from app.domain.file.enums import FileCategory, FileStatus
from app.domain.file.errors import (
    FileAccessDeniedError,
    FileAlreadyDeletedError,
    InvalidFileStateError,
)


def test_create_pending_file_sets_expected_fields() -> None:
    owner_id = uuid4()

    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key=f"candidate-service/candidate_resume/{owner_id}/resume.pdf",
    )

    assert file.id is not None
    assert file.owner.owner_service == "candidate-service"
    assert file.owner.owner_id == owner_id
    assert file.category == FileCategory.CANDIDATE_RESUME
    assert file.filename == "resume.pdf"
    assert file.content_type == "application/pdf"
    assert file.bucket == "files"
    assert file.status == FileStatus.PENDING_UPLOAD
    assert file.size_bytes is None
    assert file.deleted_at is None


def test_create_pending_file_records_file_created_event() -> None:
    owner_id = uuid4()

    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_AVATAR,
        filename="avatar.png",
        content_type="image/png",
        bucket="files",
        object_key=f"candidate-service/candidate_avatar/{owner_id}/avatar.png",
    )

    events = file.pull_events()

    assert len(events) == 1
    event = events[0]
    assert isinstance(event, FileCreated)
    assert event.file_id == file.id
    assert event.owner_service == "candidate-service"
    assert event.owner_id == owner_id
    assert event.category == FileCategory.CANDIDATE_AVATAR.value
    assert event.object_key == file.object_key


def test_pull_events_clears_event_list() -> None:
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=uuid4(),
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key="candidate-service/candidate_resume/test/resume.pdf",
    )

    first_pull = file.pull_events()
    second_pull = file.pull_events()

    assert len(first_pull) == 1
    assert second_pull == []


def test_activate_pending_file_changes_status_and_records_event() -> None:
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=uuid4(),
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key="candidate-service/candidate_resume/test/resume.pdf",
    )
    file.pull_events()

    file.activate(size_bytes=123456)

    assert file.status == FileStatus.ACTIVE
    assert file.size_bytes == 123456

    events = file.pull_events()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, FileActivated)
    assert event.file_id == file.id
    assert event.object_key == file.object_key


def test_activate_deleted_file_raises_invalid_state_error() -> None:
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

    file.mark_deleted(reason="cleanup")

    with pytest.raises(InvalidFileStateError):
        file.activate()


def test_ensure_access_allows_matching_owner() -> None:
    owner_id = uuid4()
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_AVATAR,
        filename="avatar.png",
        content_type="image/png",
        bucket="files",
        object_key="candidate-service/candidate_avatar/test/avatar.png",
    )

    file.ensure_access(
        owner_service="candidate-service",
        owner_id=owner_id,
    )


def test_ensure_access_raises_for_different_owner_service() -> None:
    owner_id = uuid4()
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_AVATAR,
        filename="avatar.png",
        content_type="image/png",
        bucket="files",
        object_key="candidate-service/candidate_avatar/test/avatar.png",
    )

    with pytest.raises(FileAccessDeniedError):
        file.ensure_access(
            owner_service="employer-service",
            owner_id=owner_id,
        )


def test_ensure_access_raises_for_different_owner_id() -> None:
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=uuid4(),
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key="candidate-service/candidate_resume/test/resume.pdf",
    )

    with pytest.raises(FileAccessDeniedError):
        file.ensure_access(
            owner_service="candidate-service",
            owner_id=uuid4(),
        )


def test_mark_deleted_changes_status_sets_deleted_at_and_records_event() -> None:
    owner_id = uuid4()
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key="candidate-service/candidate_resume/test/resume.pdf",
    )
    file.pull_events()

    file.mark_deleted(reason="deleted_by_owner")

    assert file.status == FileStatus.DELETED
    assert file.deleted_at is not None
    assert file.updated_at == file.deleted_at

    events = file.pull_events()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, FileDeleted)
    assert event.file_id == file.id
    assert event.owner_service == "candidate-service"
    assert event.owner_id == owner_id
    assert event.category == FileCategory.CANDIDATE_RESUME.value
    assert event.object_key == file.object_key
    assert event.reason == "deleted_by_owner"


def test_mark_deleted_twice_raises_file_already_deleted_error() -> None:
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

    file.mark_deleted(reason="cleanup")

    with pytest.raises(FileAlreadyDeletedError):
        file.mark_deleted(reason="cleanup_again")


def test_is_active_returns_true_only_for_active_file() -> None:
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=uuid4(),
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key="candidate-service/candidate_resume/test/resume.pdf",
    )

    assert file.is_active() is False

    file.pull_events()
    file.activate()

    assert file.is_active() is True


def test_is_deleted_returns_true_only_for_deleted_file() -> None:
    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=uuid4(),
        category=FileCategory.CANDIDATE_AVATAR,
        filename="avatar.png",
        content_type="image/png",
        bucket="files",
        object_key="candidate-service/candidate_avatar/test/avatar.png",
    )

    assert file.is_deleted() is False

    file.pull_events()
    file.mark_deleted(reason="cleanup")

    assert file.is_deleted() is True
