from __future__ import annotations

from app.application.bot.constants import ROLE_CANDIDATE, ROLE_EMPLOYER
from app.application.bot.handlers.common.callback_context import (
    ResolvedCallbackContext,
)
from app.schemas.telegram import TelegramCallbackQuery, TelegramMessage, TelegramUser


class CommandHandlersMixin:
    async def _handle_select_role_callback(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        role = str(context.payload.get("role", "")).strip().lower()
        if role not in {ROLE_CANDIDATE, ROLE_EMPLOYER}:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Некорректная роль",
                show_alert=True,
            )
            return {"status": "ignored", "reason": "invalid_role"}
        self._log_flow_event(
            "role_selected",
            telegram_user_id=actor.id,
            action_type="select_role",
            role_context=role,
        )

        await self._auth_session_service.login_via_bot(
            telegram_id=actor.id,
            role=role,
            username=actor.username,
            first_name=actor.first_name,
            last_name=actor.last_name,
            photo_url=None,
        )

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Роль выбрана",
            show_alert=False,
        )

        if callback.message is not None and callback.message.chat is not None:
            role_label = "Кандидат" if role == ROLE_CANDIDATE else "Работодатель"
            await self._telegram_client.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=f"Активная роль: {role_label}\nПодготавливаю профиль...",
            )

        await self._bootstrap_role(
            actor=actor,
            chat_id=self._resolve_chat_id(callback, actor),
            role=role,
        )

        return {"status": "processed", "action": "role_selected", "role": role}

    async def _handle_cancel_command(
        self,
        *,
        message: TelegramMessage,
        actor: TelegramUser,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)

        role = (
            state.role_context if state is not None else None
        ) or await self._auth_session_service.get_active_role(telegram_user_id=actor.id)
        if role in {ROLE_CANDIDATE, ROLE_EMPLOYER}:
            await self._bootstrap_role(
                actor=actor,
                chat_id=message.chat.id,
                role=role,
                intro_note="Текущий сценарий отменен. Возвращаю в меню.",
            )
            return {"status": "processed", "action": "cancel_to_dashboard", "role": role}

        await self._send_role_selection(
            chat_id=message.chat.id,
            actor=actor,
            intro_note="Активная роль не выбрана. Выбери роль, чтобы продолжить.",
        )
        return {"status": "processed", "action": "cancel_no_active_role"}

    async def _handle_help_command(
        self,
        *,
        message: TelegramMessage,
        actor: TelegramUser,
    ) -> dict:
        role = await self._auth_session_service.get_active_role(telegram_user_id=actor.id)
        if role == ROLE_CANDIDATE:
            text = self._build_candidate_help_message()
            action_name = "help_candidate"
            reply_markup = await self._build_candidate_back_to_dashboard_markup(
                telegram_user_id=actor.id
            )
        elif role == ROLE_EMPLOYER:
            text = self._build_employer_help_message()
            action_name = "help_employer"
            reply_markup = await self._build_employer_back_to_dashboard_markup(
                telegram_user_id=actor.id
            )
        else:
            await self._send_role_selection(
                chat_id=message.chat.id,
                actor=actor,
                intro_note=self._build_common_help_message(),
            )
            return {"status": "processed", "action": "help_common"}

        await self._telegram_client.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=reply_markup,
        )
        return {"status": "processed", "action": action_name}
