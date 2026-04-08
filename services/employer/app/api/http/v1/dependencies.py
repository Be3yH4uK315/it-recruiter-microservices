from __future__ import annotations

from collections.abc import Callable

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.contracts import (
    AuthGateway,
    CandidateGateway,
    FileGateway,
    SearchGateway,
)
from app.application.common.uow import UnitOfWork
from app.application.employers.commands.close_search_session import CloseSearchSessionHandler
from app.application.employers.commands.create_employer import CreateEmployerHandler
from app.application.employers.commands.create_search_session import CreateSearchSessionHandler
from app.application.employers.commands.delete_employer_avatar import DeleteEmployerAvatarHandler
from app.application.employers.commands.delete_employer_document import (
    DeleteEmployerDocumentHandler,
)
from app.application.employers.commands.get_next_candidate import GetNextCandidateHandler
from app.application.employers.commands.pause_search_session import PauseSearchSessionHandler
from app.application.employers.commands.replace_employer_avatar import (
    ReplaceEmployerAvatarHandler,
)
from app.application.employers.commands.replace_employer_document import (
    ReplaceEmployerDocumentHandler,
)
from app.application.employers.commands.request_contact_access import RequestContactAccessHandler
from app.application.employers.commands.respond_contact_request import RespondContactRequestHandler
from app.application.employers.commands.resume_search_session import ResumeSearchSessionHandler
from app.application.employers.commands.submit_decision import SubmitDecisionHandler
from app.application.employers.commands.update_employer import UpdateEmployerHandler
from app.application.employers.queries.get_candidate_statistics import GetCandidateStatisticsHandler
from app.application.employers.queries.get_contact_request_details import (
    GetContactRequestDetailsHandler,
)
from app.application.employers.queries.get_contact_request_status import (
    GetContactRequestStatusHandler,
)
from app.application.employers.queries.get_employer import (
    GetEmployerByTelegramHandler,
    GetEmployerHandler,
)
from app.application.employers.queries.get_employer_avatar_upload_url import (
    GetEmployerAvatarUploadUrlHandler,
)
from app.application.employers.queries.get_employer_contact_request_details import (
    GetEmployerContactRequestDetailsHandler,
)
from app.application.employers.queries.get_employer_document_upload_url import (
    GetEmployerDocumentUploadUrlHandler,
)
from app.application.employers.queries.get_employer_statistics import (
    GetEmployerStatisticsHandler,
)
from app.application.employers.queries.get_favorites import GetFavoritesHandler
from app.application.employers.queries.get_unlocked_contacts import (
    GetUnlockedContactsHandler,
)
from app.application.employers.queries.has_contact_access import HasContactAccessHandler
from app.application.employers.queries.list_candidate_pending_contact_requests import (
    ListCandidatePendingContactRequestsHandler,
)
from app.application.employers.queries.list_employer_searches import (
    ListEmployerSearchesHandler,
)
from app.config import Settings
from app.infrastructure.db.session import get_async_session
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.integrations.auth_gateway import HttpAuthGateway
from app.infrastructure.integrations.candidate_gateway import HttpCandidateGateway
from app.infrastructure.integrations.file_gateway import HttpFileGateway
from app.infrastructure.integrations.search_gateway import HttpSearchGateway


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
        cache_ttl_seconds=settings.auth_verify_cache_ttl_seconds,
        cache_max_entries=settings.auth_verify_cache_max_entries,
    )


def get_candidate_gateway(
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings_dependency),
) -> CandidateGateway:
    return HttpCandidateGateway(
        client=client,
        base_url=settings.candidate_service_url,
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


def get_search_gateway(
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings_dependency),
) -> SearchGateway:
    return HttpSearchGateway(
        client=client,
        base_url=settings.search_service_url,
        internal_token=settings.internal_service_token,
    )


def get_create_employer_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> CreateEmployerHandler:
    return CreateEmployerHandler(uow_factory)


def get_update_employer_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> UpdateEmployerHandler:
    return UpdateEmployerHandler(uow_factory)


def get_create_search_session_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> CreateSearchSessionHandler:
    return CreateSearchSessionHandler(uow_factory)


def get_get_employer_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> GetEmployerHandler:
    return GetEmployerHandler(
        uow_factory=uow_factory,
        file_gateway=file_gateway,
    )


def get_get_employer_by_telegram_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> GetEmployerByTelegramHandler:
    return GetEmployerByTelegramHandler(
        uow_factory=uow_factory,
        file_gateway=file_gateway,
    )


def get_list_employer_searches_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> ListEmployerSearchesHandler:
    return ListEmployerSearchesHandler(uow_factory)


def get_get_employer_statistics_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> GetEmployerStatisticsHandler:
    return GetEmployerStatisticsHandler(uow_factory)


def get_get_candidate_statistics_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> GetCandidateStatisticsHandler:
    return GetCandidateStatisticsHandler(uow_factory)


def get_get_next_candidate_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    search_gateway: SearchGateway = Depends(get_search_gateway),
    candidate_gateway: CandidateGateway = Depends(get_candidate_gateway),
) -> GetNextCandidateHandler:
    return GetNextCandidateHandler(
        uow_factory=uow_factory,
        search_gateway=search_gateway,
        candidate_gateway=candidate_gateway,
    )


def get_submit_decision_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> SubmitDecisionHandler:
    return SubmitDecisionHandler(uow_factory)


def get_pause_search_session_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> PauseSearchSessionHandler:
    return PauseSearchSessionHandler(uow_factory)


def get_resume_search_session_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> ResumeSearchSessionHandler:
    return ResumeSearchSessionHandler(uow_factory)


def get_close_search_session_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> CloseSearchSessionHandler:
    return CloseSearchSessionHandler(uow_factory)


def get_request_contact_access_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    candidate_gateway: CandidateGateway = Depends(get_candidate_gateway),
) -> RequestContactAccessHandler:
    return RequestContactAccessHandler(
        uow_factory=uow_factory,
        candidate_gateway=candidate_gateway,
    )


def get_respond_contact_request_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> RespondContactRequestHandler:
    return RespondContactRequestHandler(uow_factory)


def get_get_favorites_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    candidate_gateway: CandidateGateway = Depends(get_candidate_gateway),
) -> GetFavoritesHandler:
    return GetFavoritesHandler(
        uow_factory=uow_factory,
        candidate_gateway=candidate_gateway,
    )


def get_get_unlocked_contacts_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    candidate_gateway: CandidateGateway = Depends(get_candidate_gateway),
) -> GetUnlockedContactsHandler:
    return GetUnlockedContactsHandler(
        uow_factory=uow_factory,
        candidate_gateway=candidate_gateway,
    )


def get_get_contact_request_details_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    candidate_gateway: CandidateGateway = Depends(get_candidate_gateway),
) -> GetContactRequestDetailsHandler:
    return GetContactRequestDetailsHandler(
        uow_factory=uow_factory,
        candidate_gateway=candidate_gateway,
    )


def get_get_employer_contact_request_details_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    candidate_gateway: CandidateGateway = Depends(get_candidate_gateway),
) -> GetEmployerContactRequestDetailsHandler:
    return GetEmployerContactRequestDetailsHandler(
        uow_factory=uow_factory,
        candidate_gateway=candidate_gateway,
    )


def get_has_contact_access_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> HasContactAccessHandler:
    return HasContactAccessHandler(uow_factory)


def get_get_contact_request_status_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> GetContactRequestStatusHandler:
    return GetContactRequestStatusHandler(uow_factory)


def get_list_candidate_pending_contact_requests_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> ListCandidatePendingContactRequestsHandler:
    return ListCandidatePendingContactRequestsHandler(uow_factory)


def get_employer_avatar_upload_url_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> GetEmployerAvatarUploadUrlHandler:
    return GetEmployerAvatarUploadUrlHandler(
        uow_factory=uow_factory,
        file_gateway=file_gateway,
    )


def get_employer_document_upload_url_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> GetEmployerDocumentUploadUrlHandler:
    return GetEmployerDocumentUploadUrlHandler(
        uow_factory=uow_factory,
        file_gateway=file_gateway,
    )


def get_replace_employer_avatar_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> ReplaceEmployerAvatarHandler:
    return ReplaceEmployerAvatarHandler(
        uow_factory=uow_factory,
        file_gateway=file_gateway,
    )


def get_delete_employer_avatar_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> DeleteEmployerAvatarHandler:
    return DeleteEmployerAvatarHandler(
        uow_factory=uow_factory,
        file_gateway=file_gateway,
    )


def get_replace_employer_document_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> ReplaceEmployerDocumentHandler:
    return ReplaceEmployerDocumentHandler(
        uow_factory=uow_factory,
        file_gateway=file_gateway,
    )


def get_delete_employer_document_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    file_gateway: FileGateway = Depends(get_file_gateway),
) -> DeleteEmployerDocumentHandler:
    return DeleteEmployerDocumentHandler(
        uow_factory=uow_factory,
        file_gateway=file_gateway,
    )
