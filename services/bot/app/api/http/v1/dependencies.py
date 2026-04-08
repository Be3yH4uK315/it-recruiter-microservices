from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth.services.auth_session_service import AuthSessionService
from app.application.bot.services.rate_limit_service import RateLimitService
from app.application.bot.services.update_router import UpdateRouterService
from app.application.candidate.services.file_flow_service import CandidateFileFlowService
from app.application.common.contracts import AuthGateway, CandidateGateway, EmployerGateway
from app.application.employer.services.file_flow_service import EmployerFileFlowService
from app.application.state.services.conversation_state_service import ConversationStateService
from app.config import Settings, get_settings
from app.infrastructure.db.session import get_async_session
from app.infrastructure.integrations.auth_gateway import HttpAuthGateway
from app.infrastructure.integrations.candidate_gateway import HttpCandidateGateway
from app.infrastructure.integrations.employer_gateway import HttpEmployerGateway
from app.infrastructure.telegram.client import TelegramApiClient


def get_app_settings() -> Settings:
    return get_settings()


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


async def get_db_session(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[AsyncSession, None]:
    yield session


def get_auth_gateway(
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings_dependency),
) -> AuthGateway:
    return HttpAuthGateway(
        client=client,
        base_url=settings.auth_service_url,
        internal_token=settings.internal_service_token,
    )


def get_candidate_gateway(
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings_dependency),
) -> CandidateGateway:
    return HttpCandidateGateway(
        client=client,
        base_url=settings.candidate_service_url,
    )


def get_employer_gateway(
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings_dependency),
) -> EmployerGateway:
    return HttpEmployerGateway(
        client=client,
        base_url=settings.employer_service_url,
    )


def get_telegram_api_client(
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings_dependency),
) -> TelegramApiClient:
    if not settings.telegram_bot_token:
        raise RuntimeError("telegram bot token is not configured")

    return TelegramApiClient(
        client=client,
        base_url=settings.telegram_api_base_url,
        bot_token=settings.telegram_bot_token,
    )


def get_auth_session_service(
    session: AsyncSession = Depends(get_db_session),
    auth_gateway: AuthGateway = Depends(get_auth_gateway),
    settings: Settings = Depends(get_settings_dependency),
) -> AuthSessionService:
    return AuthSessionService(
        session=session,
        auth_gateway=auth_gateway,
        refresh_skew_seconds=settings.auth_access_token_refresh_skew_seconds,
    )


def get_conversation_state_service(
    session: AsyncSession = Depends(get_db_session),
) -> ConversationStateService:
    return ConversationStateService(session)


def get_candidate_file_flow_service(
    session: AsyncSession = Depends(get_db_session),
    client: httpx.AsyncClient = Depends(get_http_client),
    telegram_client: TelegramApiClient = Depends(get_telegram_api_client),
    candidate_gateway: CandidateGateway = Depends(get_candidate_gateway),
) -> CandidateFileFlowService:
    return CandidateFileFlowService(
        session=session,
        http_client=client,
        telegram_client=telegram_client,
        candidate_gateway=candidate_gateway,
    )


def get_employer_file_flow_service(
    session: AsyncSession = Depends(get_db_session),
    client: httpx.AsyncClient = Depends(get_http_client),
    telegram_client: TelegramApiClient = Depends(get_telegram_api_client),
    employer_gateway: EmployerGateway = Depends(get_employer_gateway),
) -> EmployerFileFlowService:
    return EmployerFileFlowService(
        session=session,
        http_client=client,
        telegram_client=telegram_client,
        employer_gateway=employer_gateway,
    )


def get_rate_limit_service(
    settings: Settings = Depends(get_settings_dependency),
) -> RateLimitService:
    return RateLimitService(
        enabled=settings.rate_limit_enabled,
        messages_per_second=settings.rate_limit_messages_per_second,
        callbacks_burst=settings.rate_limit_callbacks_burst,
        callbacks_cooldown_seconds=settings.rate_limit_callbacks_cooldown_seconds,
    )


def get_update_router_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings_dependency),
    telegram_client: TelegramApiClient = Depends(get_telegram_api_client),
    auth_session_service: AuthSessionService = Depends(get_auth_session_service),
    conversation_state_service: ConversationStateService = Depends(get_conversation_state_service),
    candidate_gateway: CandidateGateway = Depends(get_candidate_gateway),
    employer_gateway: EmployerGateway = Depends(get_employer_gateway),
    candidate_file_flow_service: CandidateFileFlowService = Depends(
        get_candidate_file_flow_service
    ),
    employer_file_flow_service: EmployerFileFlowService = Depends(get_employer_file_flow_service),
    rate_limit_service: RateLimitService = Depends(get_rate_limit_service),
) -> UpdateRouterService:
    return UpdateRouterService(
        session=session,
        settings=settings,
        telegram_client=telegram_client,
        auth_session_service=auth_session_service,
        conversation_state_service=conversation_state_service,
        candidate_gateway=candidate_gateway,
        employer_gateway=employer_gateway,
        candidate_file_flow_service=candidate_file_flow_service,
        employer_file_flow_service=employer_file_flow_service,
        rate_limit_service=rate_limit_service,
    )
