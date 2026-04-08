from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.exceptions import AccessDeniedError
from app.application.common.uow import UnitOfWork
from app.application.files.dto.views import FileView
from app.domain.file.errors import FileAccessDeniedError, FileNotFoundError


@dataclass(slots=True, frozen=True)
class GetFileQuery:
    file_id: UUID
    owner_service: str
    owner_id: UUID | None


@dataclass(slots=True, frozen=True)
class GetInternalFileQuery:
    file_id: UUID
    owner_service: str


class GetFileHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, query: GetFileQuery) -> FileView:
        async with self._uow_factory() as uow:
            file = await uow.files.get_by_id(query.file_id)
            if file is None:
                raise FileNotFoundError("file not found")

            try:
                file.ensure_access(
                    owner_service=query.owner_service,
                    owner_id=query.owner_id,
                )
            except FileAccessDeniedError as exc:
                raise AccessDeniedError(str(exc)) from exc

            return FileView.from_entity(file)


class GetInternalFileHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, query: GetInternalFileQuery) -> FileView:
        async with self._uow_factory() as uow:
            file = await uow.files.get_by_id(query.file_id)
            if file is None:
                raise FileNotFoundError("file not found")

            if file.owner.owner_service != query.owner_service:
                raise AccessDeniedError("access to another service file is denied")

            return FileView.from_entity(file)
