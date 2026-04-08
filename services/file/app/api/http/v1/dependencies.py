from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.contracts import ObjectStorage
from app.application.common.uow import UnitOfWork
from app.application.files.commands.cleanup_file import CleanupFileHandler
from app.application.files.commands.cleanup_stale_pending_files import (
    CleanupStalePendingFilesHandler,
)
from app.application.files.commands.create_download_url import CreateDownloadUrlHandler
from app.application.files.commands.create_upload_url import CreateUploadUrlHandler
from app.application.files.commands.delete_file import DeleteFileHandler
from app.application.files.commands.register_uploaded_file import RegisterUploadedFileHandler
from app.application.files.queries.get_file import GetFileHandler, GetInternalFileHandler
from app.config import Settings
from app.infrastructure.db.session import get_async_session
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


def get_uow_factory(
    session: AsyncSession = Depends(get_async_session),
) -> Callable[[], UnitOfWork]:
    def factory() -> UnitOfWork:
        return SqlAlchemyUnitOfWork(session)

    return factory


def get_settings_dependency(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise RuntimeError("Settings are not initialized")
    return settings


def get_storage(request: Request) -> ObjectStorage:
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        raise RuntimeError("Object storage is not initialized")
    return storage


def get_create_upload_url_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    storage: ObjectStorage = Depends(get_storage),
    settings: Settings = Depends(get_settings_dependency),
) -> CreateUploadUrlHandler:
    return CreateUploadUrlHandler(
        uow_factory=uow_factory,
        storage=storage,
        settings=settings,
    )


def get_create_download_url_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    storage: ObjectStorage = Depends(get_storage),
    settings: Settings = Depends(get_settings_dependency),
) -> CreateDownloadUrlHandler:
    return CreateDownloadUrlHandler(
        uow_factory=uow_factory,
        storage=storage,
        settings=settings,
    )


def get_delete_file_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    storage: ObjectStorage = Depends(get_storage),
) -> DeleteFileHandler:
    return DeleteFileHandler(
        uow_factory=uow_factory,
        storage=storage,
    )


def get_cleanup_file_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    storage: ObjectStorage = Depends(get_storage),
) -> CleanupFileHandler:
    return CleanupFileHandler(
        uow_factory=uow_factory,
        storage=storage,
    )


def get_cleanup_stale_pending_files_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    storage: ObjectStorage = Depends(get_storage),
) -> CleanupStalePendingFilesHandler:
    return CleanupStalePendingFilesHandler(
        uow_factory=uow_factory,
        storage=storage,
    )


def get_register_uploaded_file_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    storage: ObjectStorage = Depends(get_storage),
) -> RegisterUploadedFileHandler:
    return RegisterUploadedFileHandler(
        uow_factory=uow_factory,
        storage=storage,
    )


def get_file_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> GetFileHandler:
    return GetFileHandler(uow_factory)


def get_internal_file_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> GetInternalFileHandler:
    return GetInternalFileHandler(uow_factory)
