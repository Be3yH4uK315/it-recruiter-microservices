from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.application.auth.services.jwt_service import JwtService
from app.application.auth.services.token_hash_service import TokenHashService
from app.application.common.event_dispatch import dispatch_refresh_session_events
from app.application.common.uow import UnitOfWork
from app.domain.auth.errors import UserNotFoundError


@dataclass(slots=True, frozen=True)
class LogoutCommand:
    refresh_token: str


class LogoutHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        jwt_service: JwtService,
        token_hash_service: TokenHashService,
    ) -> None:
        self._uow_factory = uow_factory
        self._jwt_service = jwt_service
        self._token_hash_service = token_hash_service

    async def __call__(self, command: LogoutCommand) -> None:
        claims = self._jwt_service.decode_refresh_token(command.refresh_token)
        token_hash = self._token_hash_service.hash_token(command.refresh_token)

        async with self._uow_factory() as uow:
            session = await uow.refresh_sessions.get_by_token_hash(token_hash)
            if session is None:
                return

            if str(session.id) != claims.subject:
                return

            if session.revoked:
                return

            user = await uow.users.get_by_id(session.user_id)
            if user is None:
                raise UserNotFoundError(f"user {session.user_id} not found")

            session.revoke()
            await uow.refresh_sessions.save(session)
            await dispatch_refresh_session_events(
                uow=uow,
                user=user,
                refresh_session=session,
            )

            await uow.flush()
            await uow.commit()
