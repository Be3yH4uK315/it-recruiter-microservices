from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest

from app.application.common.contracts import EventMapper, ObjectStorage, OutboxPort
from app.application.common.uow import UnitOfWork
from app.application.files.commands.create_download_url import (
    CreateDownloadUrlCommand,
    CreateDownloadUrlHandler,
)
from app.config import Settings
from app.domain.file.entities import StoredFile
from app.domain.file.enums import FileCategory
from app.domain.file.repository import FileRepository


class StubStorage(ObjectStorage):
    def __init__(self) -> None:
        self.download_calls: list[tuple[str, int]] = []

    async def ensure_bucket_exists(self) -> None:
        return None

    async def generate_presigned_upload_url(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_in: int,
    ) -> str:
        raise NotImplementedError

    async def generate_presigned_download_url(
        self,
        *,
        object_key: str,
        expires_in: int,
    ) -> str:
        self.download_calls.append((object_key, expires_in))
        return f"https://example.com/{object_key}"

    async def delete_object(self, *, object_key: str) -> None:
        raise NotImplementedError

    async def object_exists(self, *, object_key: str) -> bool:
        raise NotImplementedError

    async def get_object_size(self, *, object_key: str) -> int | None:
        raise NotImplementedError


class StubFileRepository(FileRepository):
    def __init__(self, file: StoredFile | None) -> None:
        self.file = file

    async def add(self, file: StoredFile) -> None:
        raise NotImplementedError

    async def get_by_id(self, file_id: UUID) -> StoredFile | None:
        if self.file is None or self.file.id != file_id:
            return None
        return self.file

    async def get_by_object_key(self, object_key: str) -> StoredFile | None:
        raise NotImplementedError

    async def save(self, file: StoredFile) -> None:
        raise NotImplementedError

    async def delete(self, file: StoredFile) -> None:
        raise NotImplementedError

    async def list_stale_pending(self, *, created_before, limit: int) -> list[StoredFile]:
        raise NotImplementedError


class StubOutbox(OutboxPort):
    async def publish(self, *, routing_key: str, payload: dict) -> None:
        raise NotImplementedError


class StubEventMapper(EventMapper):
    def map_domain_event(self, *, event) -> list[tuple[str, dict]]:
        return []


@dataclass
class StubUnitOfWork(UnitOfWork):
    files: StubFileRepository
    outbox: StubOutbox
    event_mapper: StubEventMapper
    committed: bool = False
    rolled_back: bool = False

    async def __aenter__(self) -> "StubUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            await self.rollback()
            return
        await self.commit()

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def _build_active_file() -> StoredFile:
    file = StoredFile.create_pending(
        file_id=UUID("11111111-1111-1111-1111-111111111111"),
        owner_service="candidate-service",
        owner_id=UUID("22222222-2222-2222-2222-222222222222"),
        category=FileCategory.CANDIDATE_RESUME,
        filename="resume.pdf",
        content_type="application/pdf",
        bucket="files",
        object_key="candidate-service/candidate_resume/222/resume.pdf",
    )
    file.activate(size_bytes=1024)
    file.pull_events()
    return file


@pytest.mark.asyncio
async def test_create_download_url_generates_presign_after_uow_commit() -> None:
    file = _build_active_file()
    uow = StubUnitOfWork(
        files=StubFileRepository(file),
        outbox=StubOutbox(),
        event_mapper=StubEventMapper(),
    )
    storage = StubStorage()
    settings = Settings(
        s3_access_key="minio",
        s3_secret_key="minio123",
    )
    handler = CreateDownloadUrlHandler(
        uow_factory=lambda: uow,
        storage=storage,
        settings=settings,
    )

    result = await handler(
        CreateDownloadUrlCommand(
            file_id=file.id,
            owner_service="candidate-service",
            owner_id=file.owner.owner_id,
        )
    )

    assert uow.committed is True
    assert storage.download_calls == [
        (file.object_key, settings.default_download_url_expiration_seconds)
    ]
    assert result.file_id == file.id
    assert result.download_url == f"https://example.com/{file.object_key}"
