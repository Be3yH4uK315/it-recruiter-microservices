from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from app.application.common.event_dispatch import dispatch_refresh_session_events
from app.application.common.uow import UnitOfWork
from app.domain.auth.errors import UserNotFoundError


@dataclass(slots=True, frozen=True)
class LogoutAllCommand:
    user_id: UUID


class LogoutAllHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, command: LogoutAllCommand) -> None:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(command.user_id)
            if user is None:
                raise UserNotFoundError(f"user {command.user_id} not found")

            now = datetime.now(timezone.utc)
            sessions = await uow.refresh_sessions.list_active_by_user_id(user.id, now=now)

            for session in sessions:
                session.revoke()
                await uow.refresh_sessions.save(session)
                await dispatch_refresh_session_events(
                    uow=uow,
                    user=user,
                    refresh_session=session,
                )

            await uow.flush()
            await uow.commit()
