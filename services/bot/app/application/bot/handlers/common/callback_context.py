from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.schemas.telegram import TelegramUser

UTC = timezone.utc


@dataclass(slots=True, frozen=True)
class ResolvedCallbackContext:
    action_type: str
    payload: dict


class CallbackContextMixin:
    async def _send_role_selection(
        self,
        *,
        chat_id: int,
        actor: TelegramUser,
        intro_note: str | None = None,
    ) -> None:
        text = (
            f"👋 Привет, {actor.first_name or 'пользователь'}.\n\n"
            "Выбери роль, в которой хочешь продолжить работу:"
        )
        if intro_note:
            text = f"{intro_note}\n\n{text}"

        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=await self._build_role_selection_markup(telegram_user_id=actor.id),
        )

    async def _create_callback_context(
        self,
        *,
        telegram_user_id: int,
        action_type: str,
        payload: dict,
    ) -> str:
        token = secrets.token_urlsafe(18)
        expires_at = datetime.now(UTC) + timedelta(
            seconds=self._settings.callback_context_ttl_seconds
        )

        await self._callback_repo.create(
            token=token,
            telegram_user_id=telegram_user_id,
            action_type=action_type,
            payload=payload,
            expires_at=expires_at,
        )
        return f"{self._settings.bot_callback_prefix}{token}"

    async def _resolve_and_consume_callback_context(
        self,
        *,
        callback_data: str,
        telegram_user_id: int,
    ) -> ResolvedCallbackContext | None:
        prefix = self._settings.bot_callback_prefix
        if not callback_data.startswith(prefix):
            return None

        token = callback_data[len(prefix) :].strip()
        if not token:
            return None

        model = await self._callback_repo.get_active_for_user(
            token=token,
            telegram_user_id=telegram_user_id,
        )
        if model is None:
            return None

        await self._callback_repo.consume(model=model)
        return ResolvedCallbackContext(
            action_type=model.action_type,
            payload=model.payload,
        )
