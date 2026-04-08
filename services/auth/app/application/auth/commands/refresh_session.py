from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.application.auth.dto.views import AuthSessionView
from app.application.auth.services.jwt_service import JwtService
from app.application.auth.services.token_hash_service import TokenHashService
from app.application.common.event_dispatch import dispatch_refresh_session_events
from app.application.common.uow import UnitOfWork
from app.config import Settings
from app.domain.auth.entities import RefreshSession
from app.domain.auth.errors import (
    InvalidRefreshTokenError,
    RefreshSessionRevokedError,
    UserNotFoundError,
)
from app.domain.auth.value_objects import TokenPair


@dataclass(slots=True, frozen=True)
class RefreshSessionCommand:
    refresh_token: str


class RefreshSessionHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        jwt_service: JwtService,
        token_hash_service: TokenHashService,
        settings: Settings,
    ) -> None:
        self._uow_factory = uow_factory
        self._jwt_service = jwt_service
        self._token_hash_service = token_hash_service
        self._settings = settings

    async def __call__(self, command: RefreshSessionCommand) -> AuthSessionView:
        claims = self._jwt_service.decode_refresh_token(command.refresh_token)
        token_hash = self._token_hash_service.hash_token(command.refresh_token)

        async with self._uow_factory() as uow:
            session = await uow.refresh_sessions.get_by_token_hash(token_hash)
            if session is None:
                raise InvalidRefreshTokenError("refresh session not found")

            if str(session.id) != claims.subject:
                raise InvalidRefreshTokenError("refresh token subject mismatch")

            if session.revoked:
                raise RefreshSessionRevokedError("refresh session is revoked")

            now = datetime.now(timezone.utc)
            if session.is_expired(now):
                raise InvalidRefreshTokenError("refresh token is expired")

            user = await uow.users.get_by_id(session.user_id)
            if user is None:
                raise UserNotFoundError(f"user {session.user_id} not found")
            user.ensure_active()

            session.revoke()
            await uow.refresh_sessions.save(session)
            await dispatch_refresh_session_events(
                uow=uow,
                user=user,
                refresh_session=session,
            )

            new_session_id = uuid4()
            new_expires_at = self._jwt_service.build_refresh_expires_at()
            new_refresh_token = self._jwt_service.create_refresh_token(
                session_id=str(new_session_id),
                expires_at=new_expires_at,
            )
            new_session = RefreshSession.issue(
                id=new_session_id,
                user_id=user.id,
                token_hash=self._token_hash_service.hash_token(new_refresh_token),
                expires_at=new_expires_at,
            )
            await uow.refresh_sessions.add(new_session)
            await dispatch_refresh_session_events(
                uow=uow,
                user=user,
                refresh_session=new_session,
            )

            active_sessions = await uow.refresh_sessions.list_active_by_user_id(
                user.id,
                now=now,
            )
            active_sessions = sorted(
                active_sessions,
                key=lambda item: item.created_at,
                reverse=True,
            )

            keep_count = max(self._settings.max_active_refresh_sessions - 1, 0)
            for stale_session in active_sessions[keep_count:]:
                if stale_session.id == new_session.id:
                    continue

                stale_session.revoke()
                await uow.refresh_sessions.save(stale_session)
                await dispatch_refresh_session_events(
                    uow=uow,
                    user=user,
                    refresh_session=stale_session,
                )

            access_token, _ = self._jwt_service.create_access_token(user=user)
            await uow.flush()
            await uow.commit()

            token_pair = TokenPair(
                access_token=access_token,
                refresh_token=new_refresh_token,
                token_type="bearer",
                expires_in=self._jwt_service.access_token_ttl_seconds,
            )
            return AuthSessionView.from_domain(user=user, token_pair=token_pair)
