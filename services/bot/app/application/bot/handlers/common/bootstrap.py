from __future__ import annotations

from app.application.bot.constants import (
    ROLE_CANDIDATE,
    ROLE_EMPLOYER,
    STATE_CANDIDATE_REG_DISPLAY_NAME,
    STATE_CANDIDATE_REG_WORK_MODES,
    STATE_EMPLOYER_REG_COMPANY,
    STATE_EMPLOYER_REG_CONTACT_EMAIL,
)
from app.application.bot.handlers.common.callback_context import (
    ResolvedCallbackContext,
)
from app.application.common.gateway_errors import CandidateGatewayError, EmployerGatewayError
from app.application.observability.logging import get_logger
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser

logger = get_logger(__name__)


class BootstrapRegistrationHandlersMixin:
    async def _bootstrap_role(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        role: str,
    ) -> None:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Не удалось получить активную сессию. Нажми /start, чтобы начать заново.",
            )
            return

        if role == ROLE_CANDIDATE:
            try:
                candidate = await self._run_candidate_gateway_call(
                    telegram_user_id=actor.id,
                    access_token=access_token,
                    operation=lambda token: self._candidate_gateway.get_profile_by_telegram(
                        access_token=token,
                        telegram_id=actor.id,
                    ),
                )
            except CandidateGatewayError as exc:
                logger.warning(
                    "candidate bootstrap failed",
                    extra={"telegram_user_id": actor.id},
                    exc_info=exc,
                )
                await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
                return

            if candidate is None:
                await self._conversation_state_service.set_state(
                    telegram_user_id=actor.id,
                    role_context=ROLE_CANDIDATE,
                    state_key=STATE_CANDIDATE_REG_DISPLAY_NAME,
                    payload=None,
                )
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=(
                        "Профиль кандидата не найден.\n\n"
                        "Давай создадим минимальный профиль.\n"
                        "Сначала введи отображаемое имя."
                    ),
                    reply_markup=await self._build_stateful_cancel_markup(actor.id),
                )
                return

            stats = await self._safe_get_candidate_statistics(
                access_token=access_token,
                candidate_id=candidate.id,
            )
            recovery_note = await self._recover_pending_uploads_for_role(
                telegram_user_id=actor.id,
                role=ROLE_CANDIDATE,
                chat_id=chat_id,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    self._build_candidate_dashboard_message(
                        first_name=actor.first_name,
                        candidate=candidate,
                        statistics=stats,
                        created_now=False,
                    )
                    + (
                        f"\n\n{recovery_note}"
                        if recovery_note
                        else ""
                    )
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_candidate_dashboard_markup(actor.id),
            )
            return

        if role == ROLE_EMPLOYER:
            try:
                employer = await self._run_employer_gateway_call(
                    telegram_user_id=actor.id,
                    access_token=access_token,
                    operation=lambda token: self._employer_gateway.get_by_telegram(
                        access_token=token,
                        telegram_id=actor.id,
                    ),
                )
            except EmployerGatewayError as exc:
                logger.warning(
                    "employer bootstrap failed",
                    extra={"telegram_user_id": actor.id},
                    exc_info=exc,
                )
                await self._handle_employer_gateway_error(chat_id=chat_id, exc=exc)
                return

            if employer is None:
                await self._conversation_state_service.set_state(
                    telegram_user_id=actor.id,
                    role_context=ROLE_EMPLOYER,
                    state_key=STATE_EMPLOYER_REG_COMPANY,
                    payload=None,
                )
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=(
                        "Профиль работодателя не найден.\n\n"
                        "Введи название компании.\n"
                        "Если пока не хочешь указывать компанию, отправь `-`."
                    ),
                    parse_mode="Markdown",
                    reply_markup=await self._build_stateful_cancel_markup(actor.id),
                )
                return

            stats = await self._safe_get_employer_statistics(
                access_token=access_token,
                employer_id=employer.id,
            )
            recovery_note = await self._recover_pending_uploads_for_role(
                telegram_user_id=actor.id,
                role=ROLE_EMPLOYER,
                chat_id=chat_id,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    self._build_employer_dashboard_message(
                        first_name=actor.first_name,
                        employer=employer,
                        statistics=stats,
                        created_now=False,
                    )
                    + (
                        f"\n\n{recovery_note}"
                        if recovery_note
                        else ""
                    )
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_employer_dashboard_markup(actor.id),
            )
            return

        await self._telegram_client.send_message(
            chat_id=chat_id,
            text="Неизвестная роль. Нажми /start, чтобы начать заново.",
        )

    async def _handle_switch_role_from_menu(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Переключение роли",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=(
                f"👋 Привет, {actor.first_name or 'пользователь'}.\n\n"
                "Выбери роль, в которой хочешь продолжить работу:"
            ),
            reply_markup=await self._build_role_selection_markup(telegram_user_id=actor.id),
        )
        return {"status": "processed", "action": "switch_role_from_menu"}

    async def _handle_candidate_registration_continue(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        continue_raw = context.payload.get("continue")
        should_continue = (
            continue_raw
            if isinstance(continue_raw, bool)
            else str(continue_raw).strip().lower() in {"1", "true", "yes", "да"}
        )

        if not should_continue:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Ок, можно продолжить позже",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=(
                    "Базовую регистрацию оставили. Продолжить можно из меню профиля в любой момент."
                ),
            )
            return {"status": "processed", "action": "candidate_registration_finish_minimal"}

        await self._conversation_state_service.set_state(
            telegram_user_id=actor.id,
            role_context=ROLE_CANDIDATE,
            state_key=STATE_CANDIDATE_REG_WORK_MODES,
            payload={"selected_work_modes": []},
        )
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Продолжаем регистрацию",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=("Выбери форматы работы кнопками ниже.\n\n" "Текущий выбор: —"),
            reply_markup=await self._build_candidate_work_modes_selector_markup(
                telegram_user_id=actor.id,
                selected_modes=[],
                allow_clear=False,
            ),
        )
        return {"status": "processed", "action": "candidate_registration_continue"}

    async def _handle_employer_registration_continue(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        continue_raw = context.payload.get("continue")
        should_continue = (
            continue_raw
            if isinstance(continue_raw, bool)
            else str(continue_raw).strip().lower() in {"1", "true", "yes", "да"}
        )

        if not should_continue:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Ок, можно продолжить позже",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=(
                    "Оставили базовую регистрацию. Продолжить можно из меню профиля "
                    "в любой момент."
                ),
            )
            return {"status": "processed", "action": "employer_registration_finish_minimal"}

        await self._conversation_state_service.set_state(
            telegram_user_id=actor.id,
            role_context=ROLE_EMPLOYER,
            state_key=STATE_EMPLOYER_REG_CONTACT_EMAIL,
            payload={"telegram": self._build_telegram_contact(actor)},
        )
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Продолжаем регистрацию",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=(
                "Telegram-контакт компании синхронизирован автоматически.\n"
                "Введи email компании или отправь `-`, чтобы пропустить."
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_stateful_cancel_markup(actor.id),
        )
        return {"status": "processed", "action": "employer_registration_continue"}

    async def _handle_stateful_input_cancel(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Сценарий отменён",
            show_alert=False,
        )
        await self._send_role_selection(
            chat_id=self._resolve_chat_id(callback, actor),
            actor=actor,
        )
        if state is not None and state.role_context == ROLE_EMPLOYER:
            return {"status": "processed", "action": "stateful_input_cancel_employer"}
        return {"status": "processed", "action": "stateful_input_cancel_candidate"}

    async def _handle_employer_registration_contacts_complete(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        contacts_payload: dict,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сессия устарела. Нажми /start, чтобы выбрать роль заново.",
            )
            return {"status": "processed", "action": "session_expired"}

        try:
            employer = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
            if employer is None:
                await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text="Профиль работодателя не найден. Нажми /start, чтобы начать заново.",
                )
                return {"status": "processed", "action": "employer_not_found"}

            normalized_contacts: dict[str, str | None] = {}
            for key in ("telegram", "email", "phone", "website"):
                raw_value = contacts_payload.get(key)
                if raw_value is None:
                    normalized_contacts[key] = None
                    continue
                normalized_text = str(raw_value).strip()
                normalized_contacts[key] = normalized_text or None

            contacts_arg: dict[str, str | None] | None = (
                normalized_contacts
                if any(value for value in normalized_contacts.values())
                else None
            )
            idempotency_key = self._build_idempotency_key(
                telegram_user_id=actor.id,
                operation="employer.onboarding.complete",
                resource_id=employer.id,
            )
            updated = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.update_employer(
                    access_token=token,
                    employer_id=employer.id,
                    contacts=contacts_arg,
                    idempotency_key=idempotency_key,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer registration contacts complete failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_employer_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
        stats = await self._safe_get_employer_statistics(
            access_token=access_token,
            employer_id=updated.id,
        )
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=self._build_employer_dashboard_message(
                first_name=actor.first_name,
                employer=updated,
                statistics=stats,
                created_now=False,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": "employer_registered_extended"}
