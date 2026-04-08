from __future__ import annotations

from app.application.bot.constants import ROLE_CANDIDATE, ROLE_EMPLOYER


class CommonKeyboardsMixin:
    async def _build_role_selection_markup(
        self,
        *,
        telegram_user_id: int,
    ) -> dict:
        candidate_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="select_role",
            payload={"role": ROLE_CANDIDATE},
        )
        employer_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="select_role",
            payload={"role": ROLE_EMPLOYER},
        )
        return {
            "inline_keyboard": [
                [{"text": "🧑‍💻 Я кандидат", "callback_data": candidate_token}],
                [{"text": "🏢 Я работодатель", "callback_data": employer_token}],
            ]
        }

    async def _build_candidate_registration_continue_markup(
        self,
        telegram_user_id: int,
    ) -> dict:
        continue_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_registration_continue",
            payload={"continue": True},
        )
        stop_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_registration_continue",
            payload={"continue": False},
        )
        return {
            "inline_keyboard": [
                [{"text": "✅ Да, продолжить", "callback_data": continue_token}],
                [{"text": "⏭ Нет, пока достаточно", "callback_data": stop_token}],
            ]
        }

    async def _build_employer_registration_continue_markup(
        self,
        telegram_user_id: int,
    ) -> dict:
        continue_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_registration_continue",
            payload={"continue": True},
        )
        stop_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_registration_continue",
            payload={"continue": False},
        )
        return {
            "inline_keyboard": [
                [{"text": "✅ Да, продолжить", "callback_data": continue_token}],
                [{"text": "⏭ Нет, пока достаточно", "callback_data": stop_token}],
            ]
        }

    async def _build_stateful_cancel_markup(self, telegram_user_id: int) -> dict:
        cancel_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="stateful_input_cancel",
            payload={},
        )
        return {
            "inline_keyboard": [
                [{"text": "🛑 Отменить", "callback_data": cancel_token}],
            ]
        }
