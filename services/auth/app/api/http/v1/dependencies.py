from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth.commands.login_via_bot import LoginViaBotHandler
from app.application.auth.commands.login_via_telegram import LoginViaTelegramHandler
from app.application.auth.commands.logout import LogoutHandler
from app.application.auth.commands.logout_all import LogoutAllHandler
from app.application.auth.commands.refresh_session import RefreshSessionHandler
from app.application.auth.queries.get_user_by_id import GetUserByIdHandler
from app.application.auth.queries.get_user_by_telegram_id import GetUserByTelegramIdHandler
from app.application.auth.services.jwt_service import JwtService
from app.application.auth.services.telegram_auth_service import TelegramAuthService
from app.application.auth.services.token_hash_service import TokenHashService
from app.application.common.uow import UnitOfWork
from app.config import Settings
from app.domain.auth.value_objects import AccessTokenClaims
from app.infrastructure.auth.jwt_bearer import require_access_token_claims
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


def get_jwt_service(
    settings: Settings = Depends(get_settings_dependency),
) -> JwtService:
    return JwtService(settings)


def get_token_hash_service() -> TokenHashService:
    return TokenHashService()


def get_telegram_auth_service(
    settings: Settings = Depends(get_settings_dependency),
) -> TelegramAuthService:
    return TelegramAuthService(settings)


def get_login_via_bot_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    jwt_service: JwtService = Depends(get_jwt_service),
    token_hash_service: TokenHashService = Depends(get_token_hash_service),
    settings: Settings = Depends(get_settings_dependency),
) -> LoginViaBotHandler:
    return LoginViaBotHandler(
        uow_factory=uow_factory,
        jwt_service=jwt_service,
        token_hash_service=token_hash_service,
        settings=settings,
    )


def get_login_via_telegram_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    jwt_service: JwtService = Depends(get_jwt_service),
    telegram_auth_service: TelegramAuthService = Depends(get_telegram_auth_service),
    token_hash_service: TokenHashService = Depends(get_token_hash_service),
    settings: Settings = Depends(get_settings_dependency),
) -> LoginViaTelegramHandler:
    return LoginViaTelegramHandler(
        uow_factory=uow_factory,
        jwt_service=jwt_service,
        telegram_auth_service=telegram_auth_service,
        token_hash_service=token_hash_service,
        settings=settings,
    )


def get_refresh_session_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    jwt_service: JwtService = Depends(get_jwt_service),
    token_hash_service: TokenHashService = Depends(get_token_hash_service),
    settings: Settings = Depends(get_settings_dependency),
) -> RefreshSessionHandler:
    return RefreshSessionHandler(
        uow_factory=uow_factory,
        jwt_service=jwt_service,
        token_hash_service=token_hash_service,
        settings=settings,
    )


def get_logout_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
    jwt_service: JwtService = Depends(get_jwt_service),
    token_hash_service: TokenHashService = Depends(get_token_hash_service),
) -> LogoutHandler:
    return LogoutHandler(
        uow_factory=uow_factory,
        jwt_service=jwt_service,
        token_hash_service=token_hash_service,
    )


def get_logout_all_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> LogoutAllHandler:
    return LogoutAllHandler(uow_factory)


def get_user_by_id_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> GetUserByIdHandler:
    return GetUserByIdHandler(uow_factory)


def get_user_by_telegram_id_handler(
    uow_factory: Callable[[], UnitOfWork] = Depends(get_uow_factory),
) -> GetUserByTelegramIdHandler:
    return GetUserByTelegramIdHandler(uow_factory)


def get_current_access_claims(
    claims: AccessTokenClaims = Depends(require_access_token_claims),
) -> AccessTokenClaims:
    return claims


def get_current_user_id(
    claims: AccessTokenClaims = Depends(get_current_access_claims),
) -> UUID:
    return UUID(claims.subject)
