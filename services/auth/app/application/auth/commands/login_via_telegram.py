from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from app.application.auth.dto.views import AuthSessionView
from app.application.auth.services.jwt_service import JwtService
from app.application.auth.services.telegram_auth_service import TelegramAuthService
from app.application.auth.services.token_hash_service import TokenHashService
from app.application.common.event_dispatch import (
    dispatch_refresh_session_events,
    dispatch_user_events,
)
from app.application.common.uow import UnitOfWork
from app.config import Settings
from app.domain.auth.entities import RefreshSession, User
from app.domain.auth.enums import AuthProvider, UserRole
from app.domain.auth.value_objects import TelegramProfile, TokenPair


@dataclass(slots=True, frozen=True)
class LoginViaTelegramCommand:
    auth_payload: dict[str, str]
    role: UserRole


class LoginViaTelegramHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        jwt_service: JwtService,
        telegram_auth_service: TelegramAuthService,
        token_hash_service: TokenHashService,
        settings: Settings,
    ) -> None:
        self._uow_factory = uow_factory
        self._jwt_service = jwt_service
        self._telegram_auth_service = telegram_auth_service
        self._token_hash_service = token_hash_service
        self._settings = settings

    async def __call__(self, command: LoginViaTelegramCommand) -> AuthSessionView:
        telegram_profile = self._telegram_auth_service.validate_auth_payload(command.auth_payload)

        async with self._uow_factory() as uow:
            user = await self._get_or_create_user(
                uow=uow,
                telegram_profile=telegram_profile,
                role=command.role,
            )

            await dispatch_user_events(uow=uow, user=user)

            now = datetime.now(timezone.utc)
            await self._cleanup_user_sessions(uow=uow, user=user, now=now)

            refresh_session, refresh_token = await self._issue_refresh_session(
                uow=uow,
                user=user,
            )

            access_token, _ = self._jwt_service.create_access_token(user=user)
            await uow.flush()
            await uow.commit()

            token_pair = TokenPair(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=self._jwt_service.access_token_ttl_seconds,
            )
            return AuthSessionView.from_domain(user=user, token_pair=token_pair)

    async def _get_or_create_user(
        self,
        *,
        uow: UnitOfWork,
        telegram_profile: TelegramProfile,
        role: UserRole,
    ) -> User:
        user = await uow.users.get_by_telegram_id(telegram_profile.telegram_id)

        if user is None:
            user = User.register(
                id=uuid4(),
                telegram_profile=telegram_profile,
                role=role,
            )
            user.mark_authenticated(AuthProvider.TELEGRAM)
            await uow.users.add(user)
            return user

        user.ensure_active()
        user.update_telegram_profile(telegram_profile)
        user.change_role(role)
        user.mark_authenticated(AuthProvider.TELEGRAM)
        await uow.users.save(user)
        return user

    async def _issue_refresh_session(
        self,
        *,
        uow: UnitOfWork,
        user: User,
    ) -> tuple[RefreshSession, str]:
        refresh_session_id = uuid4()
        refresh_expires_at = self._jwt_service.build_refresh_expires_at()
        refresh_token = self._jwt_service.create_refresh_token(
            session_id=str(refresh_session_id),
            expires_at=refresh_expires_at,
        )

        refresh_session = RefreshSession.issue(
            id=refresh_session_id,
            user_id=user.id,
            token_hash=self._token_hash_service.hash_token(refresh_token),
            expires_at=refresh_expires_at,
        )
        await uow.refresh_sessions.add(refresh_session)
        await dispatch_refresh_session_events(
            uow=uow,
            user=user,
            refresh_session=refresh_session,
        )
        return refresh_session, refresh_token

    async def _cleanup_user_sessions(
        self,
        *,
        uow: UnitOfWork,
        user: User,
        now: datetime,
    ) -> None:
        await uow.refresh_sessions.delete_expired_or_revoked_by_user_id(user.id, now=now)

        sessions = await uow.refresh_sessions.list_active_by_user_id(user.id, now=now)
        sessions = sorted(sessions, key=lambda item: item.created_at, reverse=True)

        keep_count = max(self._settings.max_active_refresh_sessions - 1, 0)
        for session in sessions[keep_count:]:
            session.revoke()
            await uow.refresh_sessions.save(session)
            await dispatch_refresh_session_events(
                uow=uow,
                user=user,
                refresh_session=session,
            )
