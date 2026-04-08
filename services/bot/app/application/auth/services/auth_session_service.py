from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.contracts import AuthGateway, AuthSessionView
from app.infrastructure.db.repositories.bot_sessions import BotSessionRepository
from app.infrastructure.integrations.auth_gateway import (
    AuthGatewayUnauthorizedError,
)

UTC = timezone.utc


class AuthSessionService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        auth_gateway: AuthGateway,
        refresh_skew_seconds: int,
    ) -> None:
        self._session = session
        self._auth_gateway = auth_gateway
        self._refresh_skew_seconds = refresh_skew_seconds
        self._repo = BotSessionRepository(session)

    async def login_via_bot(
        self,
        *,
        telegram_id: int,
        role: str,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        photo_url: str | None = None,
    ) -> AuthSessionView:
        auth_session = await self._auth_gateway.login_via_bot(
            telegram_id=telegram_id,
            role=role,
            username=username,
            first_name=first_name,
            last_name=last_name,
            photo_url=photo_url,
        )
        await self._repo.save_auth_session(
            telegram_user_id=telegram_id,
            auth_session=auth_session,
        )
        return auth_session

    async def get_valid_access_token(
        self,
        *,
        telegram_user_id: int,
    ) -> str | None:
        session_model = await self._repo.get_by_telegram_user_id(telegram_user_id)
        if session_model is None:
            return None
        if not session_model.is_authorized:
            return None
        if not session_model.access_token:
            return None

        expires_at = session_model.access_token_expires_at
        if expires_at is None:
            return await self._refresh_and_return_access_token(telegram_user_id=telegram_user_id)

        now = datetime.now(UTC)
        if expires_at <= now + timedelta(seconds=self._refresh_skew_seconds):
            return await self._refresh_and_return_access_token(telegram_user_id=telegram_user_id)

        return session_model.access_token

    async def logout(
        self,
        *,
        telegram_user_id: int,
    ) -> None:
        session_model = await self._repo.get_by_telegram_user_id(telegram_user_id)
        if session_model is None:
            return

        refresh_token = session_model.refresh_token
        if refresh_token:
            try:
                await self._auth_gateway.logout(refresh_token=refresh_token)
            except Exception:
                pass

        await self._repo.clear_session(telegram_user_id=telegram_user_id)

    async def force_refresh_access_token(
        self,
        *,
        telegram_user_id: int,
    ) -> str | None:
        return await self._refresh_and_return_access_token(telegram_user_id=telegram_user_id)

    async def get_active_role(
        self,
        *,
        telegram_user_id: int,
    ) -> str | None:
        session_model = await self._repo.get_by_telegram_user_id(telegram_user_id)
        if session_model is None or not session_model.is_authorized:
            return None
        role = (session_model.active_role or "").strip().lower()
        return role or None

    async def _refresh_and_return_access_token(
        self,
        *,
        telegram_user_id: int,
    ) -> str | None:
        session_model = await self._repo.get_by_telegram_user_id(telegram_user_id)
        if session_model is None:
            return None
        if not session_model.refresh_token:
            return None

        try:
            refreshed = await self._auth_gateway.refresh_session(
                refresh_token=session_model.refresh_token
            )
        except AuthGatewayUnauthorizedError:
            await self._repo.clear_session(telegram_user_id=telegram_user_id)
            return None

        await self._repo.save_auth_session(
            telegram_user_id=telegram_user_id,
            auth_session=refreshed,
        )
        return refreshed.access_token
