from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.contracts import AuthSessionView
from app.infrastructure.db.models.bot import BotSessionModel


class BotSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> BotSessionModel | None:
        stmt = select(BotSessionModel).where(BotSessionModel.telegram_user_id == telegram_user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_auth_session(
        self,
        *,
        telegram_user_id: int,
        auth_session: AuthSessionView,
    ) -> BotSessionModel:
        session_model = await self.get_by_telegram_user_id(telegram_user_id)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=auth_session.expires_in)

        if session_model is None:
            session_model = BotSessionModel(
                telegram_user_id=telegram_user_id,
            )
            self._session.add(session_model)

        session_model.auth_user_id = auth_session.user.id
        session_model.active_role = auth_session.user.role
        session_model.access_token = auth_session.access_token
        session_model.refresh_token = auth_session.refresh_token
        session_model.token_type = auth_session.token_type
        session_model.access_token_expires_at = expires_at
        session_model.is_authorized = True
        session_model.last_login_at = now
        session_model.last_refresh_at = now

        await self._session.flush()
        return session_model

    async def clear_session(
        self,
        *,
        telegram_user_id: int,
    ) -> None:
        session_model = await self.get_by_telegram_user_id(telegram_user_id)
        if session_model is None:
            return

        session_model.auth_user_id = None
        session_model.active_role = None
        session_model.access_token = None
        session_model.refresh_token = None
        session_model.token_type = None
        session_model.access_token_expires_at = None
        session_model.is_authorized = False
        session_model.last_refresh_at = None

        await self._session.flush()
