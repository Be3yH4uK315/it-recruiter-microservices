from __future__ import annotations

from app.application.bot.constants import WIZARD_SCREEN_MESSAGE_ID_KEY
from app.application.common.telegram_api import TelegramApiError
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser

TELEGRAM_PHOTO_CAPTION_MAX_LEN = 1024


class RenderUtilsMixin:
    async def _render_callback_screen(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> None:
        if callback.message is not None and callback.message.chat is not None:
            try:
                await self._telegram_client.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
                return
            except TelegramApiError:
                pass

        await self._telegram_client.send_message(
            chat_id=self._resolve_chat_id(callback, actor),
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    async def _render_callback_screen_with_optional_photo(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        text: str,
        photo_url: str | None,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
        fallback_photo_caption: str = "🖼 Аватар профиля",
    ) -> None:
        normalized_photo_url = (photo_url or "").strip()
        if not normalized_photo_url or len(text) > TELEGRAM_PHOTO_CAPTION_MAX_LEN:
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return

        send_primary_photo = getattr(self._telegram_client, "send_primary_photo", None)
        if send_primary_photo is None:
            send_primary_photo = self._telegram_client.send_photo
        try:
            await send_primary_photo(
                chat_id=self._resolve_chat_id(callback, actor),
                photo=normalized_photo_url,
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return
        except TelegramApiError:
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return

    async def _set_state_and_render_wizard_step(
        self,
        *,
        telegram_user_id: int,
        role_context: str,
        state_key: str,
        payload: dict | None,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
        preferred_message_id: int | None = None,
    ) -> None:
        state_payload = dict(payload) if isinstance(payload, dict) else {}

        message_id: int | None = None
        if preferred_message_id is not None:
            message_id = preferred_message_id
        else:
            raw = state_payload.get(WIZARD_SCREEN_MESSAGE_ID_KEY)
            try:
                parsed = int(raw)
            except (TypeError, ValueError):
                parsed = None
            if parsed is not None and parsed > 0:
                message_id = parsed

        if message_id is not None:
            try:
                await self._telegram_client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
                state_payload[WIZARD_SCREEN_MESSAGE_ID_KEY] = message_id
                await self._conversation_state_service.set_state(
                    telegram_user_id=telegram_user_id,
                    role_context=role_context,
                    state_key=state_key,
                    payload=state_payload,
                )
                return
            except TelegramApiError:
                pass

        sent = await self._telegram_client.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        sent_message_id = sent.get("message_id")
        if isinstance(sent_message_id, int):
            state_payload[WIZARD_SCREEN_MESSAGE_ID_KEY] = sent_message_id

        await self._conversation_state_service.set_state(
            telegram_user_id=telegram_user_id,
            role_context=role_context,
            state_key=state_key,
            payload=state_payload,
        )
