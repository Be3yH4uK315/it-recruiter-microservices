from __future__ import annotations

from collections.abc import Callable

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.candidates.commands.create_candidate import CreateCandidateHandler
from app.application.candidates.commands.delete_avatar import DeleteAvatarHandler
from app.application.candidates.commands.delete_resume import DeleteResumeHandler
from app.application.candidates.commands.replace_avatar import ReplaceAvatarHandler
from app.application.candidates.commands.replace_resume import ReplaceResumeHandler
from app.application.candidates.commands.update_candidate import UpdateCandidateHandler
from app.application.candidates.queries.get_avatar_upload_url import (
    GetAvatarUploadUrlHandler,
)
from app.application.candidates.queries.get_candidate import GetCandidateHandler
from app.application.candidates.queries.get_candidate_by_telegram import (
    GetCandidateByTelegramHandler,
)
from app.application.candidates.queries.get_candidate_for_employer import (
    GetCandidateForEmployerHandler,
)
from app.application.candidates.queries.get_candidate_profile import (
    GetCandidateProfileHandler,
)
from app.application.candidates.queries.get_candidate_profile_by_telegram import (
    GetCandidateProfileByTelegramHandler,
)
from app.application.candidates.queries.get_candidate_search_document import (
    GetCandidateSearchDocumentHandler,
)
from app.application.candidates.queries.get_candidate_statistics import (
    GetCandidateStatisticsHandler,
)
from app.application.candidates.queries.get_many_candidates import (
    GetManyCandidatesHandler,
)
from app.application.candidates.queries.get_resume_upload_url import (
    GetResumeUploadUrlHandler,
)
from app.application.candidates.queries.list_candidate_search_documents import (
    ListCandidateSearchDocumentsHandler,
)
from app.application.candidates.services.contact_access_policy import ContactAccessPolicy
from app.application.common.contracts import AuthGateway, EmployerGateway, FileGateway
from app.application.common.uow import UnitOfWork
from app.config import Settings
from app.infrastructure.db.session import get_async_session
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.integrations.auth_gateway import HttpAuthGateway
from app.infrastructure.integrations.employer_gateway import HttpEmployerGateway
from app.infrastructure.integrations.file_gateway import HttpFileGateway


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


def get_http_client(request: Request) -> httpx.AsyncClient:
    client = getattr(request.app.state, "http_client", None)
    if client is None:
        raise RuntimeError("HTTP client is not initialized")
    return client


def get_auth_gateway(
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings_dependency),
) -> AuthGateway:
    return HttpAuthGateway(
        client=client,
        base_url=settings.auth_service_url,
        internal_token=settings.internal_service_token,
    )


def get_employer_gateway(
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings_dependency),
) -> EmployerGateway:
    return HttpEmployerGateway(
        client=client,
        base_url=settings.employer_service_url,
        internal_token=settings.internal_service_token,
    )


def get_file_gateway(
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings_dependency),
) -> FileGateway:
    return HttpFileGateway(
        client=client,
        base_url=settings.file_service_url,
        internal_token=settings.internal_service_token,
    )


def get_contact_access_policy() -> ContactAccessPolicy:
    return ContactAccessPolicy()


def get_create_candidate_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> CreateCandidateHandler:
    return CreateCandidateHandler(uow_factory)


def get_update_candidate_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> UpdateCandidateHandler:
    return UpdateCandidateHandler(uow_factory)


def get_replace_avatar_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> ReplaceAvatarHandler:
    return ReplaceAvatarHandler(uow_factory, file_gateway)


def get_delete_avatar_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> DeleteAvatarHandler:
    return DeleteAvatarHandler(uow_factory, file_gateway)


def get_replace_resume_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> ReplaceResumeHandler:
    return ReplaceResumeHandler(uow_factory, file_gateway)


def get_delete_resume_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> DeleteResumeHandler:
    return DeleteResumeHandler(uow_factory, file_gateway)


def get_candidate_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> GetCandidateHandler:
    return GetCandidateHandler(uow_factory)


def get_candidate_profile_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> GetCandidateProfileHandler:
    return GetCandidateProfileHandler(uow_factory, file_gateway)


def get_candidate_by_telegram_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> GetCandidateByTelegramHandler:
    return GetCandidateByTelegramHandler(uow_factory)


def get_candidate_profile_by_telegram_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> GetCandidateProfileByTelegramHandler:
    return GetCandidateProfileByTelegramHandler(uow_factory, file_gateway)


def get_many_candidates_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> GetManyCandidatesHandler:
    return GetManyCandidatesHandler(uow_factory)


def get_candidate_statistics_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    employer_gateway: EmployerGateway = Depends(get_employer_gateway),
) -> GetCandidateStatisticsHandler:
    return GetCandidateStatisticsHandler(
        uow_factory=uow_factory,
        employer_gateway=employer_gateway,
    )


def get_candidate_for_employer_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    employer_gateway: EmployerGateway = Depends(get_employer_gateway),
    access_policy: ContactAccessPolicy = Depends(get_contact_access_policy),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> GetCandidateForEmployerHandler:
    return GetCandidateForEmployerHandler(
        uow_factory=uow_factory,
        employer_gateway=employer_gateway,
        access_policy=access_policy,
        file_gateway=file_gateway,
    )


def get_avatar_upload_url_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> GetAvatarUploadUrlHandler:
    return GetAvatarUploadUrlHandler(
        uow_factory=uow_factory,
        file_gateway=file_gateway,
    )


def get_resume_upload_url_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> GetResumeUploadUrlHandler:
    return GetResumeUploadUrlHandler(
        uow_factory=uow_factory,
        file_gateway=file_gateway,
    )


def get_get_candidate_search_document_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    settings: Settings = Depends(get_settings_dependency),
) -> GetCandidateSearchDocumentHandler:
    return GetCandidateSearchDocumentHandler(
        uow_factory,
        cache_ttl_seconds=settings.internal_search_document_cache_ttl_seconds,
    )


def get_list_candidate_search_documents_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    settings: Settings = Depends(get_settings_dependency),
) -> ListCandidateSearchDocumentsHandler:
    return ListCandidateSearchDocumentsHandler(
        uow_factory,
        cache_ttl_seconds=settings.internal_search_document_list_cache_ttl_seconds,
    )
