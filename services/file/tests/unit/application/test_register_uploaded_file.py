from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest

from app.application.common.contracts import EventMapper, ObjectStorage, OutboxPort
from app.application.common.exceptions import ValidationApplicationError
from app.application.common.uow import UnitOfWork
from app.application.files.commands.register_uploaded_file import (
    RegisterUploadedFileCommand,
    RegisterUploadedFileHandler,
)
from app.domain.file.entities import StoredFile
from app.domain.file.enums import FileCategory, FileStatus
from app.domain.file.repository import FileRepository


class StubStorage(ObjectStorage):
    def __init__(self, *, size_by_key: dict[str, int | None]) -> None:
        self.size_by_key = size_by_key
        self.get_object_size_calls: list[str] = []
        self.object_exists_calls: list[str] = []

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
        raise NotImplementedError

    async def delete_object(self, *, object_key: str) -> None:
        raise NotImplementedError

    async def object_exists(self, *, object_key: str) -> bool:
        self.object_exists_calls.append(object_key)
        return object_key in self.size_by_key and self.size_by_key[object_key] is not None

    async def get_object_size(self, *, object_key: str) -> int | None:
        self.get_object_size_calls.append(object_key)
        return self.size_by_key.get(object_key)


class StubFileRepository(FileRepository):
    def __init__(self, file: StoredFile | None) -> None:
        self.file = file
        self.saved_files: list[StoredFile] = []

    async def add(self, file: StoredFile) -> None:
        raise NotImplementedError

    async def get_by_id(self, file_id: UUID) -> StoredFile | None:
        if self.file is None or self.file.id != file_id:
            return None
        return self.file

    async def get_by_object_key(self, object_key: str) -> StoredFile | None:
        raise NotImplementedError

    async def save(self, file: StoredFile) -> None:
        self.saved_files.append(file)

    async def delete(self, file: StoredFile) -> None:
        raise NotImplementedError

    async def list_stale_pending(self, *, created_before, limit: int) -> list[StoredFile]:
        raise NotImplementedError


class StubOutbox(OutboxPort):
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    async def publish(self, *, routing_key: str, payload: dict) -> None:
        self.messages.append((routing_key, payload))


class StubEventMapper(EventMapper):
    def map_domain_event(self, *, event) -> list[tuple[str, dict]]:
        return [("file.test", {"event_name": event.event_name})]


@dataclass
class StubUnitOfWork(UnitOfWork):
    files: StubFileRepository
    outbox: StubOutbox
    event_mapper: StubEventMapper
    flushed: bool = False
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
        self.flushed = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def _build_pending_file() -> StoredFile:
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
    file.pull_events()
    return file


@pytest.mark.asyncio
async def test_register_uploaded_file_uses_single_head_and_prefers_reported_size() -> None:
    file = _build_pending_file()
    storage = StubStorage(size_by_key={file.object_key: 1024})
    uow = StubUnitOfWork(
        files=StubFileRepository(file),
        outbox=StubOutbox(),
        event_mapper=StubEventMapper(),
    )
    handler = RegisterUploadedFileHandler(
        uow_factory=lambda: uow,
        storage=storage,
    )

    await handler(RegisterUploadedFileCommand(file_id=file.id, size_bytes=2048))

    assert file.status == FileStatus.ACTIVE
    assert file.size_bytes == 2048
    assert storage.get_object_size_calls == [file.object_key]
    assert storage.object_exists_calls == []
    assert len(uow.files.saved_files) == 1
    assert uow.outbox.messages == [("file.test", {"event_name": "file_activated"})]


@pytest.mark.asyncio
async def test_register_uploaded_file_rejects_missing_object() -> None:
    file = _build_pending_file()
    storage = StubStorage(size_by_key={file.object_key: None})
    uow = StubUnitOfWork(
        files=StubFileRepository(file),
        outbox=StubOutbox(),
        event_mapper=StubEventMapper(),
    )
    handler = RegisterUploadedFileHandler(
        uow_factory=lambda: uow,
        storage=storage,
    )

    with pytest.raises(ValidationApplicationError, match="file object was not uploaded"):
        await handler(RegisterUploadedFileCommand(file_id=file.id, size_bytes=2048))

    assert file.status == FileStatus.PENDING_UPLOAD
    assert storage.get_object_size_calls == [file.object_key]
    assert storage.object_exists_calls == []
