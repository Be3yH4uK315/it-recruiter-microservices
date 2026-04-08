from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.file.entities import StoredFile
from app.domain.file.enums import FileCategory, FileStatus
from app.infrastructure.db.repositories.file import SqlAlchemyFileRepository


@pytest.mark.asyncio
async def test_add_and_get_file_by_id(db_session: AsyncSession) -> None:
    repository = SqlAlchemyFileRepository(db_session)
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
    file.pull_events()

    await repository.add(file)
    await db_session.commit()

    loaded = await repository.get_by_id(file.id)

    assert loaded is not None
    assert loaded.id == file.id
    assert loaded.owner.owner_service == "candidate-service"
    assert loaded.owner.owner_id == owner_id
    assert loaded.category == FileCategory.CANDIDATE_RESUME
    assert loaded.filename == "resume.pdf"
    assert loaded.content_type == "application/pdf"
    assert loaded.bucket == "files"
    assert loaded.object_key == file.object_key
    assert loaded.status == FileStatus.PENDING_UPLOAD
    assert loaded.size_bytes is None
    assert loaded.deleted_at is None


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_file_not_found(db_session: AsyncSession) -> None:
    repository = SqlAlchemyFileRepository(db_session)

    result = await repository.get_by_id(uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_get_by_object_key_returns_file(db_session: AsyncSession) -> None:
    repository = SqlAlchemyFileRepository(db_session)
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
    file.pull_events()

    await repository.add(file)
    await db_session.commit()

    loaded = await repository.get_by_object_key(file.object_key)

    assert loaded is not None
    assert loaded.id == file.id
    assert loaded.owner.owner_service == "candidate-service"
    assert loaded.owner.owner_id == owner_id
    assert loaded.category == FileCategory.CANDIDATE_AVATAR
    assert loaded.filename == "avatar.png"
    assert loaded.object_key == file.object_key


@pytest.mark.asyncio
async def test_get_by_object_key_returns_none_when_missing(db_session: AsyncSession) -> None:
    repository = SqlAlchemyFileRepository(db_session)

    result = await repository.get_by_object_key("missing/object/key")

    assert result is None


@pytest.mark.asyncio
async def test_update_activated_file(db_session: AsyncSession) -> None:
    repository = SqlAlchemyFileRepository(db_session)
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
    file.pull_events()

    await repository.add(file)
    await db_session.commit()

    file.activate(size_bytes=2048)
    file.pull_events()

    await repository.save(file)
    await db_session.commit()

    loaded = await repository.get_by_id(file.id)

    assert loaded is not None
    assert loaded.status == FileStatus.ACTIVE
    assert loaded.size_bytes == 2048
    assert loaded.deleted_at is None


@pytest.mark.asyncio
async def test_update_deleted_file(db_session: AsyncSession) -> None:
    repository = SqlAlchemyFileRepository(db_session)
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
    file.pull_events()

    await repository.add(file)
    await db_session.commit()

    file.mark_deleted(reason="cleanup")
    file.pull_events()

    await repository.save(file)
    await db_session.commit()

    loaded = await repository.get_by_id(file.id)

    assert loaded is not None
    assert loaded.status == FileStatus.DELETED
    assert loaded.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_removes_file_record(db_session: AsyncSession) -> None:
    repository = SqlAlchemyFileRepository(db_session)
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
    file.pull_events()

    await repository.add(file)
    await db_session.commit()

    existing = await repository.get_by_id(file.id)
    assert existing is not None

    await repository.delete(file)
    await db_session.commit()

    deleted = await repository.get_by_id(file.id)
    assert deleted is None


@pytest.mark.asyncio
async def test_can_store_multiple_files_for_different_categories(db_session: AsyncSession) -> None:
    repository = SqlAlchemyFileRepository(db_session)
    owner_id = uuid4()

    avatar = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_AVATAR,
        filename="avatar.png",
        content_type="image/png",
        bucket="files",
        object_key=f"candidate-service/candidate_avatar/{owner_id}/avatar.png",
    )
    avatar.pull_events()

    resume = StoredFile.create_pending(
        owner_service="candidate-service",
        owner_id=owner_id,
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key=f"candidate-service/candidate_resume/{owner_id}/resume.pdf",
    )
    resume.pull_events()

    await repository.add(avatar)
    await repository.add(resume)
    await db_session.commit()

    loaded_avatar = await repository.get_by_id(avatar.id)
    loaded_resume = await repository.get_by_id(resume.id)

    assert loaded_avatar is not None
    assert loaded_resume is not None
    assert loaded_avatar.category == FileCategory.CANDIDATE_AVATAR
    assert loaded_resume.category == FileCategory.CANDIDATE_RESUME
    assert loaded_avatar.object_key != loaded_resume.object_key


@pytest.mark.asyncio
async def test_update_preserves_owner_and_object_key(db_session: AsyncSession) -> None:
    repository = SqlAlchemyFileRepository(db_session)
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
    file.pull_events()

    await repository.add(file)
    await db_session.commit()

    file.activate(size_bytes=999)
    file.pull_events()

    await repository.save(file)
    await db_session.commit()

    loaded = await repository.get_by_id(file.id)

    assert loaded is not None
    assert loaded.owner.owner_service == "candidate-service"
    assert loaded.owner.owner_id == owner_id
    assert loaded.object_key == f"candidate-service/candidate_avatar/{owner_id}/avatar.png"
    assert loaded.size_bytes == 999
