from __future__ import annotations

from uuid import UUID

import pytest

from app.domain.file.entities import StoredFile
from app.domain.file.enums import FileCategory, FileStatus
from app.infrastructure.db.repositories.file import SqlAlchemyFileRepository


@pytest.mark.asyncio
async def test_get_file_returns_file_for_matching_owner(client, db_session) -> None:
    repository = SqlAlchemyFileRepository(db_session)
    owner_id = UUID("11111111-1111-1111-1111-111111111111")

    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key=f"candidate-service/candidate_resume/{owner_id}/resume.pdf",
    )
    file.pull_events()

    await repository.add(file)
    await db_session.commit()

    response = await client.get(
        f"/internal/files/{file.id}",
        params={"owner_service": "candidate-service"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(file.id)
    assert payload["owner_service"] == "candidate-service"
    assert payload["owner_id"] == str(owner_id)


@pytest.mark.asyncio
async def test_get_file_returns_403_for_other_owner_service(client, db_session) -> None:
    repository = SqlAlchemyFileRepository(db_session)
    owner_id = UUID("11111111-1111-1111-1111-111111111111")

    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_AVATAR,
        filename="avatar.png",
        content_type="image/png",
        bucket="files",
        object_key=f"candidate-service/candidate_avatar/{owner_id}/avatar.png",
    )
    file.pull_events()

    await repository.add(file)
    await db_session.commit()

    response = await client.get(
        f"/internal/files/{file.id}",
        params={"owner_service": "employer-service"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "access to another service file is denied"


@pytest.mark.asyncio
async def test_create_download_url_activates_file_when_object_exists(
    client,
    db_session,
    storage_stub,
) -> None:
    repository = SqlAlchemyFileRepository(db_session)
    owner_id = UUID("11111111-1111-1111-1111-111111111111")

    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key=f"candidate-service/candidate_resume/{owner_id}/resume.pdf",
    )
    file.pull_events()
    file.activate(size_bytes=123)
    file.pull_events()

    await repository.add(file)
    await db_session.commit()
    storage_stub.existing_keys.add(file.object_key)

    response = await client.get(
        f"/internal/files/{file.id}/download-url",
        params={
            "owner_service": "candidate-service",
            "owner_id": str(owner_id),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["file_id"] == str(file.id)
    assert payload["method"] == "GET"
    assert payload["expires_in"] == 3600

    loaded = await repository.get_by_id(file.id)
    assert loaded is not None
    assert loaded.status == FileStatus.ACTIVE


@pytest.mark.asyncio
async def test_create_download_url_returns_422_for_pending_file(client, db_session) -> None:
    repository = SqlAlchemyFileRepository(db_session)
    owner_id = UUID("11111111-1111-1111-1111-111111111111")

    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key=f"candidate-service/candidate_resume/{owner_id}/resume.pdf",
    )
    file.pull_events()

    await repository.add(file)
    await db_session.commit()

    response = await client.get(
        f"/internal/files/{file.id}/download-url",
        params={
            "owner_service": "candidate-service",
            "owner_id": str(owner_id),
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "file is not uploaded yet"


@pytest.mark.asyncio
async def test_cleanup_file_marks_deleted_and_removes_object(
    client,
    db_session,
    storage_stub,
) -> None:
    repository = SqlAlchemyFileRepository(db_session)
    owner_id = UUID("11111111-1111-1111-1111-111111111111")

    file = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_AVATAR,
        filename="avatar.png",
        content_type="image/png",
        bucket="files",
        object_key=f"candidate-service/candidate_avatar/{owner_id}/avatar.png",
    )
    file.pull_events()
    file.activate(size_bytes=512)
    file.pull_events()

    await repository.add(file)
    await db_session.commit()
    storage_stub.existing_keys.add(file.object_key)

    response = await client.post(
        f"/internal/files/{file.id}/cleanup",
        json={
            "reason": "candidate_avatar_replaced",
            "requested_by_service": "candidate-service",
        },
    )

    assert response.status_code == 204
    assert file.object_key in storage_stub.deleted_keys

    loaded = await repository.get_by_id(file.id)
    assert loaded is not None
    assert loaded.status == FileStatus.DELETED
