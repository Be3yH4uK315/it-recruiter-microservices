from __future__ import annotations

from datetime import date
from urllib.parse import urlparse

from app.application.bot.constants import (
    CONTACT_VISIBILITY_HIDDEN,
    CONTACT_VISIBILITY_ON_REQUEST,
    CONTACT_VISIBILITY_PUBLIC,
    EMPLOYER_SEARCH_ABOUT_MAX_LEN,
    EMPLOYER_SEARCH_ROLE_MAX_LEN,
    EMPLOYER_SEARCH_ROLE_MIN_LEN,
    EMPLOYER_SEARCH_TITLE_MAX_LEN,
    EMPLOYER_SEARCH_TITLE_MIN_LEN,
    ROLE_CANDIDATE,
    ROLE_EMPLOYER,
    STATE_CANDIDATE_CONTACT_REQUEST_AWAIT_ID,
    STATE_CANDIDATE_EDIT_ABOUT_ME,
    STATE_CANDIDATE_EDIT_CONTACT_EMAIL,
    STATE_CANDIDATE_EDIT_CONTACT_PHONE,
    STATE_CANDIDATE_EDIT_CONTACT_TELEGRAM,
    STATE_CANDIDATE_EDIT_CONTACTS_VISIBILITY,
    STATE_CANDIDATE_EDIT_DISPLAY_NAME,
    STATE_CANDIDATE_EDIT_EDUCATION,
    STATE_CANDIDATE_EDIT_ENGLISH_LEVEL,
    STATE_CANDIDATE_EDIT_EXPERIENCES,
    STATE_CANDIDATE_EDIT_HEADLINE_ROLE,
    STATE_CANDIDATE_EDIT_LOCATION,
    STATE_CANDIDATE_EDIT_PROJECTS,
    STATE_CANDIDATE_EDIT_SALARY,
    STATE_CANDIDATE_EDIT_SKILLS,
    STATE_CANDIDATE_EDIT_STATUS,
    STATE_CANDIDATE_EDIT_WORK_MODES,
    STATE_CANDIDATE_FILE_AWAIT_AVATAR,
    STATE_CANDIDATE_FILE_AWAIT_RESUME,
    STATE_CANDIDATE_REG_ABOUT_ME,
    STATE_CANDIDATE_REG_CONTACT_EMAIL,
    STATE_CANDIDATE_REG_CONTACT_PHONE,
    STATE_CANDIDATE_REG_CONTACTS_VISIBILITY,
    STATE_CANDIDATE_REG_DISPLAY_NAME,
    STATE_CANDIDATE_REG_EDUCATION,
    STATE_CANDIDATE_REG_ENGLISH_LEVEL,
    STATE_CANDIDATE_REG_EXPERIENCES,
    STATE_CANDIDATE_REG_HEADLINE_ROLE,
    STATE_CANDIDATE_REG_LOCATION,
    STATE_CANDIDATE_REG_PROJECTS,
    STATE_CANDIDATE_REG_SALARY,
    STATE_CANDIDATE_REG_SKILLS,
    STATE_CANDIDATE_REG_WORK_MODES,
    STATE_EMPLOYER_EDIT_COMPANY,
    STATE_EMPLOYER_EDIT_CONTACT_EMAIL,
    STATE_EMPLOYER_EDIT_CONTACT_PHONE,
    STATE_EMPLOYER_EDIT_CONTACT_TELEGRAM,
    STATE_EMPLOYER_EDIT_CONTACT_WEBSITE,
    STATE_EMPLOYER_FILE_AWAIT_AVATAR,
    STATE_EMPLOYER_FILE_AWAIT_DOCUMENT,
    STATE_EMPLOYER_REG_COMPANY,
    STATE_EMPLOYER_REG_CONTACT_EMAIL,
    STATE_EMPLOYER_REG_CONTACT_PHONE,
    STATE_EMPLOYER_REG_CONTACT_TELEGRAM,
    STATE_EMPLOYER_REG_CONTACT_WEBSITE,
    STATE_EMPLOYER_SEARCH_ABOUT,
    STATE_EMPLOYER_SEARCH_ENGLISH,
    STATE_EMPLOYER_SEARCH_EXPERIENCE,
    STATE_EMPLOYER_SEARCH_LOCATION,
    STATE_EMPLOYER_SEARCH_MUST_SKILLS,
    STATE_EMPLOYER_SEARCH_NICE_SKILLS,
    STATE_EMPLOYER_SEARCH_ROLE,
    STATE_EMPLOYER_SEARCH_SALARY,
    STATE_EMPLOYER_SEARCH_TITLE,
    STATE_EMPLOYER_SEARCH_WORK_MODES,
)
from app.application.bot.handlers.common.callback_context import (
    ResolvedCallbackContext,
)
from app.application.common.gateway_errors import CandidateGatewayError, EmployerGatewayError
from app.application.observability.logging import get_logger
from app.application.state.services.conversation_state_service import ConversationStateView
from app.schemas.telegram import TelegramCallbackQuery, TelegramMessage, TelegramUser

logger = get_logger(__name__)


class StatefulMessageHandlersMixin:
    async def _send_stateful_message(
        self,
        *,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> None:
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    async def _return_stateful_message(
        self,
        *,
        chat_id: int,
        text: str,
        action: str,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        await self._send_stateful_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return {"status": "processed", "action": action}

    async def _set_state_and_prompt_stateful_step(
        self,
        *,
        telegram_user_id: int,
        role_context: str,
        state_key: str,
        payload: dict | None,
        chat_id: int,
        text: str,
        action: str,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        await self._conversation_state_service.set_state(
            telegram_user_id=telegram_user_id,
            role_context=role_context,
            state_key=state_key,
            payload=payload,
        )
        return await self._return_stateful_message(
            chat_id=chat_id,
            text=text,
            action=action,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    async def _clear_state_and_return_stateful_message(
        self,
        *,
        telegram_user_id: int,
        chat_id: int,
        text: str,
        action: str,
        parse_mode: str | None = None,
        reply_markup: dict | None = None,
    ) -> dict:
        await self._conversation_state_service.clear_state(telegram_user_id=telegram_user_id)
        return await self._return_stateful_message(
            chat_id=chat_id,
            text=text,
            action=action,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    async def _render_candidate_dashboard_completion_screen(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        access_token: str,
        candidate,
        created_now: bool,
        reply_markup: dict | None,
        follow_up_text: str | None = None,
    ) -> None:
        stats = await self._safe_get_candidate_statistics(
            access_token=access_token,
            candidate_id=candidate.id,
        )
        message_text = self._build_candidate_dashboard_message(
            first_name=actor.first_name,
            candidate=candidate,
            statistics=stats,
            created_now=created_now,
        )
        if follow_up_text:
            message_text = f"{message_text}\n\n{follow_up_text}"
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )

    async def _render_employer_dashboard_completion_screen(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        access_token: str,
        employer,
        created_now: bool,
        reply_markup: dict | None,
        follow_up_text: str | None = None,
    ) -> None:
        stats = await self._safe_get_employer_statistics(
            access_token=access_token,
            employer_id=employer.id,
        )
        message_text = self._build_employer_dashboard_message(
            first_name=actor.first_name,
            employer=employer,
            statistics=stats,
            created_now=created_now,
        )
        if follow_up_text:
            message_text = f"{message_text}\n\n{follow_up_text}"
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )

    async def _complete_employer_search_text_step(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        payload: dict,
        step: str,
        saved_action: str,
        saved_from_confirm_action: str,
        next_state_key: str,
        next_text: str,
        next_step: str,
        next_parse_mode: str | None = None,
        next_allow_skip: bool = False,
    ) -> dict:
        if self._is_employer_search_edit_step(payload, step=step):
            await self._render_employer_search_confirm_step(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                payload=payload,
            )
            return {"status": "processed", "action": saved_from_confirm_action}

        await self._set_state_and_render_wizard_step(
            telegram_user_id=actor.id,
            role_context=ROLE_EMPLOYER,
            state_key=next_state_key,
            payload=payload,
            chat_id=chat_id,
            text=next_text,
            parse_mode=next_parse_mode,
            reply_markup=await self._build_employer_search_wizard_controls_markup(
                telegram_user_id=actor.id,
                step=next_step,
                allow_skip=next_allow_skip,
            ),
        )
        return {"status": "processed", "action": saved_action}

    async def _complete_employer_search_render_step(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        payload: dict,
        step: str,
        saved_action: str,
        saved_from_confirm_action: str,
        render_next,
    ) -> dict:
        if self._is_employer_search_edit_step(payload, step=step):
            await self._render_employer_search_confirm_step(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                payload=payload,
            )
            return {"status": "processed", "action": saved_from_confirm_action}

        await render_next()
        return {"status": "processed", "action": saved_action}

    async def _handle_stateful_message(
        self,
        *,
        message: TelegramMessage,
        actor: TelegramUser,
        state: ConversationStateView,
    ) -> dict:
        chat_id = message.chat.id if message.chat is not None else actor.id
        self._log_flow_event(
            "stateful_message_received",
            telegram_user_id=actor.id,
            role_context=state.role_context,
            state_key=state.state_key,
            extra={"message_id": message.message_id},
        )
        if state.state_key in {
            STATE_CANDIDATE_FILE_AWAIT_AVATAR,
            STATE_CANDIDATE_FILE_AWAIT_RESUME,
        }:
            return await self._handle_candidate_file_upload_state(
                message=message,
                actor=actor,
                state=state,
                chat_id=chat_id,
            )
        if state.state_key in {
            STATE_EMPLOYER_FILE_AWAIT_AVATAR,
            STATE_EMPLOYER_FILE_AWAIT_DOCUMENT,
        }:
            return await self._handle_employer_file_upload_state(
                message=message,
                actor=actor,
                state=state,
                chat_id=chat_id,
            )

        text = (message.text or "").strip()

        if not text:
            await self._send_stateful_message(
                chat_id=chat_id,
                text="Отправь текстовым сообщением нужное значение.",
            )
            return {"status": "processed", "action": "empty_stateful_message"}

        if state.state_key == STATE_CANDIDATE_REG_DISPLAY_NAME:
            display_name, error_text = self._normalize_profile_name_value(
                raw_value=text,
                field_label="Отображаемое имя",
            )
            if error_text is not None:
                await self._send_stateful_message(
                    chat_id=chat_id,
                    text=error_text,
                )
                return {"status": "processed", "action": "candidate_registration_display_name_invalid"}
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_HEADLINE_ROLE,
                payload={"display_name": display_name},
                chat_id=chat_id,
                text=self._build_structured_prompt(
                    title="Введи основную роль",
                    instruction="Укажи основную роль, по которой кандидат ищет работу.",
                    examples=["Python Developer"],
                ),
                action="candidate_registration_display_name_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_CANDIDATE_REG_HEADLINE_ROLE:
            display_name = self._extract_payload_text(state.payload, "display_name")
            if not display_name:
                return await self._set_state_and_prompt_stateful_step(
                    telegram_user_id=actor.id,
                    role_context=ROLE_CANDIDATE,
                    state_key=STATE_CANDIDATE_REG_DISPLAY_NAME,
                    payload=None,
                    chat_id=chat_id,
                    text=self._build_structured_prompt(
                        title="Состояние регистрации сброшено",
                        instruction="Введи отображаемое имя кандидата ещё раз.",
                        examples=["Иван Петров"],
                    ),
                    action="candidate_registration_reset",
                    parse_mode="Markdown",
                )

            access_token = await self._auth_session_service.get_valid_access_token(
                telegram_user_id=actor.id
            )
            if access_token is None:
                return await self._clear_state_and_return_stateful_message(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    text="Сессия устарела. Нажми /start, чтобы выбрать роль заново.",
                    action="session_expired",
                )

            telegram_contact = self._build_telegram_contact(actor)
            idempotency_key = self._build_idempotency_key(
                telegram_user_id=actor.id,
                operation="candidate.create",
            )

            try:
                candidate = await self._run_candidate_gateway_call(
                    telegram_user_id=actor.id,
                    access_token=access_token,
                    operation=lambda token: self._candidate_gateway.create_candidate(
                        access_token=token,
                        display_name=display_name,
                        headline_role=text,
                        telegram_contact=telegram_contact,
                        idempotency_key=idempotency_key,
                    ),
                )
            except CandidateGatewayError as exc:
                logger.warning(
                    "candidate registration failed",
                    extra={"telegram_user_id": actor.id},
                    exc_info=exc,
                )
                await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
                await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
                return {"status": "processed", "action": "candidate_gateway_error"}

            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._render_candidate_dashboard_completion_screen(
                actor=actor,
                chat_id=chat_id,
                access_token=access_token,
                candidate=candidate,
                created_now=True,
                reply_markup=await self._build_candidate_registration_continue_markup(actor.id),
                follow_up_text=(
                    "Базовая регистрация завершена.\n"
                    "Хочешь продолжить и заполнить дополнительные поля профиля?"
                ),
            )
            return {"status": "processed", "action": "candidate_registered_minimal"}

        if state.state_key == STATE_CANDIDATE_REG_WORK_MODES:
            await self._send_stateful_message(
                chat_id=chat_id,
                text=(
                    "Полная регистрация кандидата\n\n"
                    "Выбери формат работы кнопками ниже.\n\n"
                    f"Текущий выбор: {self._format_work_modes_choice_for_prompt(state.payload)}"
                ),
                reply_markup=await self._build_candidate_work_modes_selector_markup(
                    telegram_user_id=actor.id,
                    selected_modes=self._extract_selected_work_modes_payload(state.payload),
                    allow_clear=False,
                ),
            )
            return {
                "status": "processed",
                "action": "candidate_registration_work_modes_keyboard_prompt",
            }

        if state.state_key == STATE_CANDIDATE_REG_CONTACTS_VISIBILITY:
            await self._send_stateful_message(
                chat_id=chat_id,
                text=(
                    "Полная регистрация кандидата\n\n"
                    "Выбери видимость контактов кнопками ниже.\n\n"
                    f"Текущий выбор: {self._format_contacts_visibility_for_prompt(state.payload)}"
                ),
                reply_markup=await self._build_candidate_contacts_visibility_selector_markup(
                    telegram_user_id=actor.id,
                    selected_visibility=self._extract_selected_contacts_visibility_payload(
                        state.payload
                    ),
                ),
            )
            return {
                "status": "processed",
                "action": "candidate_registration_contacts_visibility_keyboard_prompt",
            }

        if state.state_key == STATE_CANDIDATE_REG_ENGLISH_LEVEL:
            await self._send_stateful_message(
                chat_id=chat_id,
                text=(
                    "Полная регистрация кандидата\n\n"
                    "Выбери уровень английского кнопками ниже.\n\n"
                    f"Текущий выбор: {self._format_english_level_for_prompt(state.payload)}"
                ),
                reply_markup=await self._build_candidate_english_level_selector_markup(
                    telegram_user_id=actor.id,
                    selected_level=self._extract_selected_english_level_payload(state.payload),
                    allow_clear=True,
                ),
            )
            return {
                "status": "processed",
                "action": "candidate_registration_english_keyboard_prompt",
            }

        if state.state_key == STATE_CANDIDATE_REG_SALARY:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            work_modes_payload = payload.get("work_modes")
            contacts_visibility_payload = payload.get("contacts_visibility")
            english_level_payload = payload.get("english_level")

            work_modes = work_modes_payload if isinstance(work_modes_payload, list) else None
            contacts_visibility = (
                str(contacts_visibility_payload).strip().lower()
                if contacts_visibility_payload is not None
                else None
            )
            english_level = (
                str(english_level_payload).strip().upper()
                if isinstance(english_level_payload, str)
                else None
            )

            if not work_modes or contacts_visibility not in {
                CONTACT_VISIBILITY_PUBLIC,
                CONTACT_VISIBILITY_ON_REQUEST,
                CONTACT_VISIBILITY_HIDDEN,
            }:
                await self._conversation_state_service.set_state(
                    telegram_user_id=actor.id,
                    role_context=ROLE_CANDIDATE,
                    state_key=STATE_CANDIDATE_REG_WORK_MODES,
                    payload={"selected_work_modes": []},
                )
                await self._send_stateful_message(
                    chat_id=chat_id,
                    text=(
                        "Не удалось восстановить данные продолжения регистрации.\n"
                        "Повторим с шага выбора формата работы."
                    ),
                    reply_markup=await self._build_candidate_work_modes_selector_markup(
                        telegram_user_id=actor.id,
                        selected_modes=[],
                        allow_clear=False,
                    ),
                )
                return {"status": "processed", "action": "candidate_registration_payload_reset"}

            normalized_salary = text.strip()
            if normalized_salary.lower() in {"-", "skip", "пропустить", "нет"}:
                salary_min: int | None = None
                salary_max: int | None = None
                currency: str | None = None
            else:
                parsed_salary = self._parse_search_salary(normalized_salary)
                if parsed_salary is None:
                    return await self._return_stateful_message(
                        chat_id=chat_id,
                        text="Формат зарплаты: `min max currency`, например `250000 350000 RUB`.",
                        action="candidate_registration_salary_invalid",
                        parse_mode="Markdown",
                    )
                salary_min, salary_max, currency = parsed_salary
                if salary_min < 0 or salary_max < 0 or salary_max < salary_min:
                    return await self._return_stateful_message(
                        chat_id=chat_id,
                        text="Проверь значения: min/max >= 0 и max >= min.",
                        action="candidate_registration_salary_invalid",
                    )
                if currency is not None and (len(currency) < 3 or len(currency) > 5):
                    return await self._return_stateful_message(
                        chat_id=chat_id,
                        text="Валюта должна быть кодом вроде RUB, USD, EUR.",
                        action="candidate_registration_salary_invalid",
                    )
            payload["work_modes"] = work_modes
            payload["contacts_visibility"] = contacts_visibility
            payload["english_level"] = english_level
            payload["salary_min"] = salary_min
            payload["salary_max"] = salary_max
            payload["currency"] = currency
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_LOCATION,
                payload=payload,
                chat_id=chat_id,
                text=(
                    self._build_structured_prompt(
                        title="Укажи локацию",
                        instruction="Введи город, страну или другой удобный формат.",
                        examples=["Москва", "Berlin"],
                        footer="Или отправь `-`, чтобы пропустить.",
                    )
                ),
                action="candidate_registration_salary_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_CANDIDATE_REG_LOCATION:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["location"] = self._normalize_optional_user_input(text)
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_ABOUT_ME,
                payload=payload,
                chat_id=chat_id,
                text=(
                    self._build_structured_prompt(
                        title="Напиши кратко о себе",
                        instruction="Коротко опиши профиль, сильные стороны или цели.",
                        footer="Или отправь `-`, чтобы пропустить.",
                    )
                ),
                action="candidate_registration_location_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_CANDIDATE_REG_ABOUT_ME:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["about_me"] = self._normalize_optional_user_input(text)
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_CONTACT_EMAIL,
                payload=payload,
                chat_id=chat_id,
                text=(
                    self._build_structured_prompt(
                        title="Укажи email",
                        instruction="Добавь контактный email для связи.",
                        examples=["name@example.com"],
                        footer="Или отправь `-`, чтобы пропустить.",
                    )
                ),
                action="candidate_registration_about_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_CANDIDATE_REG_CONTACT_EMAIL:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            value = self._normalize_optional_user_input(text)
            if value is not None:
                value, error_text = self._normalize_contact_value(
                    contact_key="email",
                    raw_value=value,
                )
                if error_text is not None:
                    return await self._return_stateful_message(
                        chat_id=chat_id,
                        text=error_text,
                        action="candidate_registration_contact_email_invalid",
                        parse_mode="Markdown",
                    )
            payload["contact_email"] = value
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_CONTACT_PHONE,
                payload=payload,
                chat_id=chat_id,
                text=(
                    self._build_structured_prompt(
                        title="Укажи телефон",
                        instruction="Добавь контактный номер телефона.",
                        examples=["+7 999 123-45-67"],
                        footer="Или отправь `-`, чтобы пропустить.",
                    )
                ),
                action="candidate_registration_contact_email_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_CANDIDATE_REG_CONTACT_PHONE:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            value = self._normalize_optional_user_input(text)
            if value is not None:
                value, error_text = self._normalize_contact_value(
                    contact_key="phone",
                    raw_value=value,
                )
                if error_text is not None:
                    return await self._return_stateful_message(
                        chat_id=chat_id,
                        text=error_text,
                        action="candidate_registration_contact_phone_invalid",
                        parse_mode="Markdown",
                    )
            payload["contact_phone"] = value
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_SKILLS,
                payload=payload,
                chat_id=chat_id,
                text=(
                    self._build_structured_prompt(
                        title="Введи навыки",
                        instruction="Добавляй по одному навыку на строку.",
                        details=[
                            "`skill; kind; level`",
                            "Разделитель: `;` или `|`.",
                            "kind: `hard`, `soft`, `tool`, `language`.",
                            "level: 1..5, можно оставить пустым.",
                        ],
                        examples=["Python; hard; 5"],
                        footer="Чтобы пропустить, отправь `-`.",
                    )
                ),
                action="candidate_registration_contact_phone_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_CANDIDATE_REG_SKILLS:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed_skills, error_text = self._parse_candidate_registration_skills(text)
            if error_text is not None:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text=error_text,
                    action="candidate_registration_skills_invalid",
                    parse_mode="Markdown",
                )
            payload["skills"] = parsed_skills
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_EDUCATION,
                payload=payload,
                chat_id=chat_id,
                text=(
                    self._build_structured_prompt(
                        title="Введи образование",
                        instruction="Добавляй по одной записи на строку.",
                        details=[
                            "`level; institution; year`",
                            "Разделитель: `;` или `|`.",
                        ],
                        examples=["Bachelor; NSU; 2022"],
                        footer="Чтобы пропустить, отправь `-`.",
                    )
                ),
                action="candidate_registration_skills_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_CANDIDATE_REG_EDUCATION:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed_education, error_text = self._parse_candidate_registration_education(text)
            if error_text is not None:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text=error_text,
                    action="candidate_registration_education_invalid",
                    parse_mode="Markdown",
                )
            payload["education"] = parsed_education
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_EXPERIENCES,
                payload=payload,
                chat_id=chat_id,
                text=(
                    self._build_structured_prompt(
                        title="Введи опыт",
                        instruction="Добавляй по одной записи на строку.",
                        details=[
                            "`company; position; start_date; end_date; responsibilities`",
                            "Разделитель: `;` или `|`.",
                            "Дата: `YYYY-MM-DD`, `end_date` можно оставить пустым.",
                        ],
                        examples=[
                            "Acme; Backend Developer; 2023-01-01; 2024-02-01; FastAPI и PostgreSQL"
                        ],
                        footer="Чтобы пропустить, отправь `-`.",
                    )
                ),
                action="candidate_registration_education_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_CANDIDATE_REG_EXPERIENCES:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed_experiences, error_text = self._parse_candidate_registration_experiences(text)
            if error_text is not None:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text=error_text,
                    action="candidate_registration_experiences_invalid",
                    parse_mode="Markdown",
                )
            payload["experiences"] = parsed_experiences
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_PROJECTS,
                payload=payload,
                chat_id=chat_id,
                text=(
                    self._build_structured_prompt(
                        title="Введи проекты",
                        instruction="Добавляй по одному проекту на строку.",
                        details=[
                            "`title; description; link1,link2`",
                            "Разделитель между полями: `;` или `|`.",
                            "Ссылки опциональны, только `http`/`https`.",
                        ],
                        examples=["ATS Bot; Telegram recruiting bot; https://github.com/org/repo"],
                        footer="Чтобы пропустить, отправь `-`.",
                    )
                ),
                action="candidate_registration_experiences_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_CANDIDATE_REG_PROJECTS:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed_projects, error_text = self._parse_candidate_registration_projects(text)
            if error_text is not None:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text=error_text,
                    action="candidate_registration_projects_invalid",
                    parse_mode="Markdown",
                )
            payload["projects"] = parsed_projects
            return await self._complete_candidate_full_registration(
                actor=actor,
                chat_id=chat_id,
                payload=payload,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_DISPLAY_NAME:
            return await self._handle_candidate_edit_submit(
                actor=actor,
                chat_id=chat_id,
                field_name="display_name",
                raw_value=text,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_HEADLINE_ROLE:
            return await self._handle_candidate_edit_submit(
                actor=actor,
                chat_id=chat_id,
                field_name="headline_role",
                raw_value=text,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_LOCATION:
            location = None if text.lower() in {"-", "skip", "пропустить", "нет"} else text
            return await self._handle_candidate_edit_submit(
                actor=actor,
                chat_id=chat_id,
                field_name="location",
                raw_value=location,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_ABOUT_ME:
            about_me = None if text.lower() in {"-", "skip", "пропустить", "нет"} else text
            return await self._handle_candidate_edit_submit(
                actor=actor,
                chat_id=chat_id,
                field_name="about_me",
                raw_value=about_me,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_WORK_MODES:
            await self._send_stateful_message(
                chat_id=chat_id,
                text=(
                    "Для выбора формата работы используй кнопки ниже.\n\n"
                    f"Текущий выбор: {self._format_work_modes_choice_for_prompt(state.payload)}"
                ),
                reply_markup=await self._build_candidate_work_modes_selector_markup(
                    telegram_user_id=actor.id,
                    selected_modes=self._extract_selected_work_modes_payload(state.payload),
                    allow_clear=True,
                ),
            )
            return {"status": "processed", "action": "candidate_edit_work_modes_keyboard_prompt"}

        if state.state_key == STATE_CANDIDATE_EDIT_ENGLISH_LEVEL:
            await self._send_stateful_message(
                chat_id=chat_id,
                text=(
                    "Для выбора английского используй кнопки ниже.\n\n"
                    f"Текущий выбор: {self._format_english_level_for_prompt(state.payload)}"
                ),
                reply_markup=await self._build_candidate_english_level_selector_markup(
                    telegram_user_id=actor.id,
                    selected_level=self._extract_selected_english_level_payload(state.payload),
                    allow_clear=True,
                ),
            )
            return {"status": "processed", "action": "candidate_edit_english_keyboard_prompt"}

        if state.state_key == STATE_CANDIDATE_EDIT_STATUS:
            await self._send_stateful_message(
                chat_id=chat_id,
                text=(
                    "Для выбора статуса используй кнопки ниже.\n\n"
                    f"Текущий выбор: {self._format_candidate_status_for_prompt(state.payload)}"
                ),
                reply_markup=await self._build_candidate_status_selector_markup(
                    telegram_user_id=actor.id,
                    selected_status=self._extract_selected_candidate_status_payload(state.payload),
                ),
            )
            return {"status": "processed", "action": "candidate_edit_status_keyboard_prompt"}

        if state.state_key == STATE_CANDIDATE_EDIT_SALARY:
            return await self._handle_candidate_salary_submit(
                actor=actor,
                chat_id=chat_id,
                raw_value=text,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_SKILLS:
            return await self._handle_candidate_skills_submit(
                actor=actor,
                chat_id=chat_id,
                raw_value=text,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_EDUCATION:
            return await self._handle_candidate_education_submit(
                actor=actor,
                chat_id=chat_id,
                raw_value=text,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_EXPERIENCES:
            return await self._handle_candidate_experiences_submit(
                actor=actor,
                chat_id=chat_id,
                raw_value=text,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_PROJECTS:
            return await self._handle_candidate_projects_submit(
                actor=actor,
                chat_id=chat_id,
                raw_value=text,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_CONTACTS_VISIBILITY:
            await self._send_stateful_message(
                chat_id=chat_id,
                text=(
                    "Для выбора видимости контактов используй кнопки ниже.\n\n"
                    f"Текущий выбор: {self._format_contacts_visibility_for_prompt(state.payload)}"
                ),
                reply_markup=await self._build_candidate_contacts_visibility_selector_markup(
                    telegram_user_id=actor.id,
                    selected_visibility=self._extract_selected_contacts_visibility_payload(
                        state.payload
                    ),
                ),
            )
            return {"status": "processed", "action": "candidate_edit_visibility_keyboard_prompt"}

        if state.state_key == STATE_CANDIDATE_EDIT_CONTACT_TELEGRAM:
            return await self._handle_candidate_contact_submit(
                actor=actor,
                chat_id=chat_id,
                contact_key="telegram",
                raw_value=text,
                allow_clear=False,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_CONTACT_EMAIL:
            email = None if text.lower() in {"-", "skip", "пропустить", "нет"} else text
            return await self._handle_candidate_contact_submit(
                actor=actor,
                chat_id=chat_id,
                contact_key="email",
                raw_value=email,
                allow_clear=True,
            )

        if state.state_key == STATE_CANDIDATE_EDIT_CONTACT_PHONE:
            phone = None if text.lower() in {"-", "skip", "пропустить", "нет"} else text
            return await self._handle_candidate_contact_submit(
                actor=actor,
                chat_id=chat_id,
                contact_key="phone",
                raw_value=phone,
                allow_clear=True,
            )

        if state.state_key == STATE_CANDIDATE_CONTACT_REQUEST_AWAIT_ID:
            return await self._handle_candidate_contact_request_lookup(
                actor=actor,
                chat_id=chat_id,
                raw_request_id=text,
            )

        if state.state_key == STATE_EMPLOYER_REG_COMPANY:
            if text.lower() in {"-", "skip", "пропустить", "нет"}:
                company = None
            else:
                company, error_text = self._normalize_profile_name_value(
                    raw_value=text,
                    field_label="Название компании",
                )
                if error_text is not None:
                    return await self._return_stateful_message(
                        chat_id=chat_id,
                        text=error_text,
                        action="employer_registration_company_invalid",
                    )
            access_token = await self._auth_session_service.get_valid_access_token(
                telegram_user_id=actor.id
            )
            if access_token is None:
                return await self._clear_state_and_return_stateful_message(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    text="Сессия устарела. Нажми /start, чтобы выбрать роль заново.",
                    action="session_expired",
                )

            idempotency_key = self._build_idempotency_key(
                telegram_user_id=actor.id,
                operation="employer.create",
            )

            try:
                employer = await self._run_employer_gateway_call(
                    telegram_user_id=actor.id,
                    access_token=access_token,
                    operation=lambda token: self._employer_gateway.create_employer(
                        access_token=token,
                        telegram_id=actor.id,
                        company=company,
                        idempotency_key=idempotency_key,
                    ),
                )
            except EmployerGatewayError as exc:
                logger.warning(
                    "employer registration failed",
                    extra={"telegram_user_id": actor.id},
                    exc_info=exc,
                )
                await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
                await self._handle_employer_gateway_error(chat_id=chat_id, exc=exc)
                return {"status": "processed", "action": "employer_gateway_error"}

            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._render_employer_dashboard_completion_screen(
                actor=actor,
                chat_id=chat_id,
                access_token=access_token,
                employer=employer,
                created_now=True,
                reply_markup=await self._build_employer_registration_continue_markup(actor.id),
                follow_up_text=(
                    "Базовая регистрация завершена.\n"
                    "Хочешь продолжить и заполнить дополнительные поля профиля?"
                ),
            )
            return {"status": "processed", "action": "employer_registered_minimal"}

        if state.state_key == STATE_EMPLOYER_REG_CONTACT_TELEGRAM:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["telegram"] = self._build_telegram_contact(actor)
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_REG_CONTACT_EMAIL,
                payload=payload,
                chat_id=chat_id,
                text=(
                    self._build_structured_prompt(
                        title="Введи email компании",
                        instruction="Telegram-контакт компании синхронизирован автоматически.",
                        examples=["jobs@example.com"],
                        footer="Или отправь `-`, чтобы пропустить.",
                    )
                ),
                action="employer_registration_contact_telegram_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_EMPLOYER_REG_CONTACT_EMAIL:
            value = self._normalize_optional_user_input(text)
            if value is not None:
                value, error_text = self._normalize_contact_value(
                    contact_key="email",
                    raw_value=value,
                )
                if error_text is not None:
                    return await self._return_stateful_message(
                        chat_id=chat_id,
                        text=error_text,
                        action="employer_registration_contact_email_invalid",
                        parse_mode="Markdown",
                    )
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["email"] = value or None
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_REG_CONTACT_PHONE,
                payload=payload,
                chat_id=chat_id,
                text=self._build_structured_prompt(
                    title="Введи phone компании",
                    instruction="Укажи контактный телефон компании.",
                    examples=["+7 999 123-45-67"],
                    footer="Или отправь `-`, чтобы пропустить.",
                ),
                action="employer_registration_contact_email_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_EMPLOYER_REG_CONTACT_PHONE:
            value = self._normalize_optional_user_input(text)
            if value is not None:
                value, error_text = self._normalize_contact_value(
                    contact_key="phone",
                    raw_value=value,
                )
                if error_text is not None:
                    return await self._return_stateful_message(
                        chat_id=chat_id,
                        text=error_text,
                        action="employer_registration_contact_phone_invalid",
                        parse_mode="Markdown",
                    )
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["phone"] = value or None
            return await self._set_state_and_prompt_stateful_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_REG_CONTACT_WEBSITE,
                payload=payload,
                chat_id=chat_id,
                text=self._build_structured_prompt(
                    title="Введи website компании",
                    instruction="Укажи адрес сайта компании.",
                    examples=["https://company.com"],
                    footer="Или отправь `-`, чтобы пропустить.",
                ),
                action="employer_registration_contact_phone_saved",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )

        if state.state_key == STATE_EMPLOYER_REG_CONTACT_WEBSITE:
            value = self._normalize_optional_user_input(text)
            if value is not None:
                value, error_text = self._normalize_contact_value(
                    contact_key="website",
                    raw_value=value,
                )
                if error_text is not None:
                    return await self._return_stateful_message(
                        chat_id=chat_id,
                        text=error_text,
                        action="employer_registration_contact_website_invalid",
                        parse_mode="Markdown",
                    )
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["website"] = value or None
            return await self._handle_employer_registration_contacts_complete(
                actor=actor,
                chat_id=chat_id,
                contacts_payload=payload,
            )

        if state.state_key == STATE_EMPLOYER_EDIT_COMPANY:
            company = None if text.lower() in {"-", "skip", "пропустить", "нет"} else text
            return await self._handle_employer_edit_company_submit(
                actor=actor,
                chat_id=chat_id,
                company=company,
            )

        if state.state_key == STATE_EMPLOYER_EDIT_CONTACT_TELEGRAM:
            value = None if text.lower() in {"-", "skip", "пропустить", "нет"} else text
            return await self._handle_employer_contact_submit(
                actor=actor,
                chat_id=chat_id,
                contact_key="telegram",
                raw_value=value,
            )

        if state.state_key == STATE_EMPLOYER_EDIT_CONTACT_EMAIL:
            value = None if text.lower() in {"-", "skip", "пропустить", "нет"} else text
            return await self._handle_employer_contact_submit(
                actor=actor,
                chat_id=chat_id,
                contact_key="email",
                raw_value=value,
            )

        if state.state_key == STATE_EMPLOYER_EDIT_CONTACT_PHONE:
            value = None if text.lower() in {"-", "skip", "пропустить", "нет"} else text
            return await self._handle_employer_contact_submit(
                actor=actor,
                chat_id=chat_id,
                contact_key="phone",
                raw_value=value,
            )

        if state.state_key == STATE_EMPLOYER_EDIT_CONTACT_WEBSITE:
            value = None if text.lower() in {"-", "skip", "пропустить", "нет"} else text
            return await self._handle_employer_contact_submit(
                actor=actor,
                chat_id=chat_id,
                contact_key="website",
                raw_value=value,
            )

        if state.state_key == STATE_EMPLOYER_SEARCH_TITLE:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            title = text.strip()
            if len(title) < EMPLOYER_SEARCH_TITLE_MIN_LEN:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text=(
                        "Название должно быть не короче "
                        f"{EMPLOYER_SEARCH_TITLE_MIN_LEN} символов."
                    ),
                    action="employer_search_title_invalid",
                )
            if len(title) > EMPLOYER_SEARCH_TITLE_MAX_LEN:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text=(
                        "Название слишком длинное. Максимум "
                        f"{EMPLOYER_SEARCH_TITLE_MAX_LEN} символов."
                    ),
                    action="employer_search_title_too_long",
                )

            payload["title"] = title
            return await self._complete_employer_search_text_step(
                actor=actor,
                chat_id=chat_id,
                payload=payload,
                step="title",
                saved_action="employer_search_title_saved",
                saved_from_confirm_action="employer_search_title_saved_from_confirm",
                next_state_key=STATE_EMPLOYER_SEARCH_ROLE,
                next_text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Теперь введи основную роль для поиска. Например: Python Backend Developer."
                ),
                next_step="role",
            )

        if state.state_key == STATE_EMPLOYER_SEARCH_ROLE:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            title = self._extract_payload_text(payload, "title")
            role = text.strip()
            if not title:
                await self._set_state_and_render_wizard_step(
                    telegram_user_id=actor.id,
                    role_context=ROLE_EMPLOYER,
                    state_key=STATE_EMPLOYER_SEARCH_TITLE,
                    payload=payload,
                    chat_id=chat_id,
                    text=(
                        "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                        "Не удалось восстановить title поиска. Введи название поиска заново."
                    ),
                    reply_markup=await self._build_employer_search_wizard_controls_markup(
                        telegram_user_id=actor.id,
                        step="title",
                        allow_skip=False,
                        allow_back=False,
                    ),
                )
                return {"status": "processed", "action": "employer_search_reset"}
            if len(role) < EMPLOYER_SEARCH_ROLE_MIN_LEN:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text=f"Роль должна быть не короче {EMPLOYER_SEARCH_ROLE_MIN_LEN} символов.",
                    action="employer_search_role_invalid",
                )
            if len(role) > EMPLOYER_SEARCH_ROLE_MAX_LEN:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text=f"Роль слишком длинная. Максимум {EMPLOYER_SEARCH_ROLE_MAX_LEN} символов.",
                    action="employer_search_role_too_long",
                )

            payload["role"] = role
            return await self._complete_employer_search_text_step(
                actor=actor,
                chat_id=chat_id,
                payload=payload,
                step="role",
                saved_action="employer_search_role_saved",
                saved_from_confirm_action="employer_search_role_saved_from_confirm",
                next_state_key=STATE_EMPLOYER_SEARCH_MUST_SKILLS,
                next_text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Введи обязательные навыки через запятую.\n"
                    "Можно указать уровень: `Python:4, FastAPI:3`.\n"
                    "Отправь `-`, если шаг пропускаем."
                ),
                next_step="must_skills",
                next_parse_mode="Markdown",
                next_allow_skip=True,
            )

        if state.state_key == STATE_EMPLOYER_SEARCH_MUST_SKILLS:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed = self._parse_search_skill_list(text)
            if parsed is None:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text="Неверный формат навыков. Пример: `Python:4, FastAPI:3` или `-`.",
                    action="employer_search_must_skills_invalid",
                    parse_mode="Markdown",
                )
            payload["must_skills"] = parsed
            return await self._complete_employer_search_text_step(
                actor=actor,
                chat_id=chat_id,
                payload=payload,
                step="must_skills",
                saved_action="employer_search_must_skills_saved",
                saved_from_confirm_action="employer_search_must_skills_saved_from_confirm",
                next_state_key=STATE_EMPLOYER_SEARCH_NICE_SKILLS,
                next_text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Введи желательные навыки через запятую.\n"
                    "Пример: `Docker:3, AWS`.\n"
                    "Отправь `-`, если шаг пропускаем."
                ),
                next_step="nice_skills",
                next_parse_mode="Markdown",
                next_allow_skip=True,
            )

        if state.state_key == STATE_EMPLOYER_SEARCH_NICE_SKILLS:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed = self._parse_search_skill_list(text)
            if parsed is None:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text="Неверный формат навыков. Пример: `Docker:3, AWS` или `-`.",
                    action="employer_search_nice_skills_invalid",
                    parse_mode="Markdown",
                )
            payload["nice_skills"] = parsed
            return await self._complete_employer_search_text_step(
                actor=actor,
                chat_id=chat_id,
                payload=payload,
                step="nice_skills",
                saved_action="employer_search_nice_skills_saved",
                saved_from_confirm_action="employer_search_nice_skills_saved_from_confirm",
                next_state_key=STATE_EMPLOYER_SEARCH_EXPERIENCE,
                next_text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    f"{self._build_search_experience_prompt()}"
                ),
                next_step="experience",
                next_parse_mode="Markdown",
                next_allow_skip=True,
            )

        if state.state_key == STATE_EMPLOYER_SEARCH_EXPERIENCE:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            experience = self._parse_search_experience_range(text)
            if experience is None:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text=self._build_search_experience_invalid_text(),
                    action="employer_search_experience_invalid",
                    parse_mode="Markdown",
                )
            payload["experience_min"] = experience[0]
            payload["experience_max"] = experience[1]
            return await self._complete_employer_search_text_step(
                actor=actor,
                chat_id=chat_id,
                payload=payload,
                step="experience",
                saved_action="employer_search_experience_saved",
                saved_from_confirm_action="employer_search_experience_saved_from_confirm",
                next_state_key=STATE_EMPLOYER_SEARCH_LOCATION,
                next_text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Введи желаемую локацию (город/страна) или `-`, чтобы пропустить."
                ),
                next_step="location",
                next_allow_skip=True,
            )

        if state.state_key == STATE_EMPLOYER_SEARCH_LOCATION:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["location"] = self._normalize_optional_user_input(text)
            async def _render_next_work_modes_step() -> None:
                await self._render_employer_search_work_modes_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                    allow_skip=True,
                )

            return await self._complete_employer_search_render_step(
                actor=actor,
                chat_id=chat_id,
                payload=payload,
                step="location",
                saved_action="employer_search_location_saved",
                saved_from_confirm_action="employer_search_location_saved_from_confirm",
                render_next=_render_next_work_modes_step,
            )

        if state.state_key == STATE_EMPLOYER_SEARCH_WORK_MODES:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            await self._render_employer_search_work_modes_step(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                payload=payload,
                allow_skip=True,
            )
            return {"status": "processed", "action": "employer_search_work_modes_keyboard_prompt"}

        if state.state_key == STATE_EMPLOYER_SEARCH_SALARY:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            salary = self._parse_search_salary(text)
            if salary is None:
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text=self._build_search_salary_invalid_text(),
                    action="employer_search_salary_invalid",
                    parse_mode="Markdown",
                )
            payload["salary_min"] = salary[0]
            payload["salary_max"] = salary[1]
            payload["currency"] = salary[2]
            async def _render_next_english_step() -> None:
                await self._render_employer_search_english_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                    allow_skip=True,
                )

            return await self._complete_employer_search_render_step(
                actor=actor,
                chat_id=chat_id,
                payload=payload,
                step="salary",
                saved_action="employer_search_salary_saved",
                saved_from_confirm_action="employer_search_salary_saved_from_confirm",
                render_next=_render_next_english_step,
            )

        if state.state_key == STATE_EMPLOYER_SEARCH_ENGLISH:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            await self._render_employer_search_english_step(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                payload=payload,
                allow_skip=True,
            )
            return {"status": "processed", "action": "employer_search_english_keyboard_prompt"}

        if state.state_key == STATE_EMPLOYER_SEARCH_ABOUT:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            normalized_about = self._normalize_optional_user_input(text)
            if (
                normalized_about is not None
                and len(normalized_about) > EMPLOYER_SEARCH_ABOUT_MAX_LEN
            ):
                return await self._return_stateful_message(
                    chat_id=chat_id,
                    text=(
                        "Описание слишком длинное. Максимум "
                        f"{EMPLOYER_SEARCH_ABOUT_MAX_LEN} символов."
                    ),
                    action="employer_search_about_too_long",
                )
            payload["about_me"] = normalized_about
            async def _render_next_confirm_step() -> None:
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )

            return await self._complete_employer_search_render_step(
                actor=actor,
                chat_id=chat_id,
                payload=payload,
                step="about",
                saved_action="employer_search_about_saved",
                saved_from_confirm_action="employer_search_about_saved",
                render_next=_render_next_confirm_step,
            )

        await self._send_stateful_message(
            chat_id=chat_id,
            text="Неизвестное состояние. Нажми /start, чтобы начать заново.",
        )
        return {"status": "processed", "action": "unknown_state"}

    async def _complete_candidate_full_registration(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        payload: dict,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            return await self._clear_state_and_return_stateful_message(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                text="Сессия устарела. Нажми /start, чтобы выбрать роль заново.",
                action="session_expired",
            )

        try:
            candidate = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.get_profile_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
            if candidate is None:
                return await self._clear_state_and_return_stateful_message(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    text="Профиль кандидата не найден. Нажми /start, чтобы начать заново.",
                    action="candidate_not_found",
                )

            idempotency_key = self._build_idempotency_key(
                telegram_user_id=actor.id,
                operation="candidate.onboarding.complete",
                resource_id=candidate.id,
            )
            existing_contacts = dict(candidate.contacts or {})
            telegram_contact = existing_contacts.get("telegram")
            if not telegram_contact:
                existing_contacts["telegram"] = self._build_telegram_contact(actor)
            if "contact_email" in payload:
                existing_contacts["email"] = payload.get("contact_email")
            if "contact_phone" in payload:
                existing_contacts["phone"] = payload.get("contact_phone")
            updated = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.update_candidate_profile(
                    access_token=token,
                    candidate_id=candidate.id,
                    location=payload.get("location"),
                    work_modes=payload.get("work_modes"),
                    about_me=payload.get("about_me"),
                    contacts_visibility=payload.get("contacts_visibility"),
                    salary_min=payload.get("salary_min"),
                    salary_max=payload.get("salary_max"),
                    currency=payload.get("currency"),
                    contacts=existing_contacts,
                    english_level=payload.get("english_level"),
                    skills=payload.get("skills"),
                    education=payload.get("education"),
                    experiences=payload.get("experiences"),
                    projects=payload.get("projects"),
                    idempotency_key=idempotency_key,
                ),
            )
        except CandidateGatewayError as exc:
            logger.warning(
                "candidate registration full profile submit failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "candidate_gateway_error"}

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
        await self._render_candidate_dashboard_completion_screen(
            actor=actor,
            chat_id=chat_id,
            access_token=access_token,
            candidate=updated,
            created_now=False,
            reply_markup=await self._build_candidate_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": "candidate_registered_extended"}

    def _parse_candidate_registration_skills(
        self, raw_value: str
    ) -> tuple[list[dict] | None, str | None]:
        normalized = raw_value.strip()
        if normalized.lower() in {"-", "skip", "пропустить", "нет"}:
            return ([], None)
        lines = [line.strip() for line in raw_value.splitlines() if line.strip()]
        if not lines:
            return (None, "Добавь хотя бы одну строку навыка или отправь `-` для пропуска.")
        parsed: list[dict] = []
        for index, line in enumerate(lines, start=1):
            parts = self._split_candidate_structured_line(line, expected_parts=3)
            if len(parts) < 2:
                return (None, f"Строка {index}: формат `skill; kind; level`.")
            skill = parts[0]
            kind = parts[1].lower()
            level_raw = parts[2] if len(parts) == 3 else ""
            if not skill:
                return (None, f"Строка {index}: skill не может быть пустым.")
            if kind not in {"hard", "soft", "tool", "language"}:
                return (None, f"Строка {index}: kind должен быть hard/soft/tool/language.")
            level: int | None = None
            if level_raw:
                try:
                    level = int(level_raw)
                except ValueError:
                    return (None, f"Строка {index}: level должен быть числом 1..5 или пустым.")
                if level < 1 or level > 5:
                    return (None, f"Строка {index}: level должен быть в диапазоне 1..5.")
            parsed.append({"skill": skill, "kind": kind, "level": level})
        return (parsed, None)

    def _parse_candidate_registration_education(
        self, raw_value: str
    ) -> tuple[list[dict] | None, str | None]:
        normalized = raw_value.strip()
        if normalized.lower() in {"-", "skip", "пропустить", "нет"}:
            return ([], None)
        lines = [line.strip() for line in raw_value.splitlines() if line.strip()]
        if not lines:
            return (None, "Добавь хотя бы одну строку образования или отправь `-` для пропуска.")
        parsed: list[dict] = []
        for index, line in enumerate(lines, start=1):
            parts = self._split_candidate_structured_line(line, expected_parts=3)
            if len(parts) != 3:
                return (None, f"Строка {index}: формат `level; institution; year`.")
            level, institution, year_raw = parts
            if not level or not institution:
                return (None, f"Строка {index}: level и institution обязательны.")
            try:
                year = int(year_raw)
            except ValueError:
                return (None, f"Строка {index}: year должен быть числом.")
            if year < 1950 or year > 2100:
                return (None, f"Строка {index}: year должен быть в диапазоне 1950..2100.")
            parsed.append({"level": level, "institution": institution, "year": year})
        return (parsed, None)

    def _parse_candidate_registration_experiences(
        self, raw_value: str
    ) -> tuple[list[dict] | None, str | None]:
        normalized = raw_value.strip()
        if normalized.lower() in {"-", "skip", "пропустить", "нет"}:
            return ([], None)
        lines = [line.strip() for line in raw_value.splitlines() if line.strip()]
        if not lines:
            return (None, "Добавь хотя бы одну строку опыта или отправь `-` для пропуска.")
        parsed: list[dict] = []
        for index, line in enumerate(lines, start=1):
            parts = self._split_candidate_structured_line(line, expected_parts=5)
            company, position, start_raw, end_raw, responsibilities_raw = parts
            if not company or not position or not start_raw:
                return (None, f"Строка {index}: company, position и `start_date` обязательны.")
            try:
                start_date = date.fromisoformat(start_raw)
            except ValueError:
                return (None, f"Строка {index}: `start_date` в формате YYYY-MM-DD.")
            end_date: str | None = None
            if end_raw:
                try:
                    parsed_end = date.fromisoformat(end_raw)
                except ValueError:
                    return (None, f"Строка {index}: `end_date` в формате YYYY-MM-DD или пусто.")
                end_date = parsed_end.isoformat()
            parsed.append(
                {
                    "company": company,
                    "position": position,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date,
                    "responsibilities": responsibilities_raw or None,
                }
            )
        return (parsed, None)

    def _parse_candidate_registration_projects(
        self, raw_value: str
    ) -> tuple[list[dict] | None, str | None]:
        normalized = raw_value.strip()
        if normalized.lower() in {"-", "skip", "пропустить", "нет"}:
            return ([], None)
        lines = [line.strip() for line in raw_value.splitlines() if line.strip()]
        if not lines:
            return (None, "Добавь хотя бы одну строку проекта или отправь `-` для пропуска.")
        parsed: list[dict] = []
        for index, line in enumerate(lines, start=1):
            parts = self._split_candidate_structured_line(line, expected_parts=3)
            title, description, links_raw = parts
            if not title:
                return (None, f"Строка {index}: title обязателен.")
            links: list[str] = []
            if links_raw:
                for link in [item.strip() for item in links_raw.split(",") if item.strip()]:
                    parsed_url = urlparse(link)
                    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                        return (
                            None,
                            f"Строка {index}: ссылка `{link}` должна быть http/https URL.",
                        )
                    links.append(link)
            parsed.append(
                {
                    "title": title,
                    "description": description or None,
                    "links": links,
                }
            )
        return (parsed, None)

    @staticmethod
    def _split_candidate_structured_line(line: str, *, expected_parts: int) -> list[str]:
        normalized = line.strip()
        if "|" in normalized:
            separator = "|"
        elif ";" in normalized:
            separator = ";"
        else:
            return [normalized]

        parts = [part.strip() for part in normalized.split(separator, expected_parts - 1)]
        while len(parts) < expected_parts:
            parts.append("")
        return parts

    async def _handle_candidate_choice_work_mode_toggle(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key not in {
            STATE_CANDIDATE_REG_WORK_MODES,
            STATE_CANDIDATE_EDIT_WORK_MODES,
        }:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Шаг выбора формата работы устарел.",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_work_modes_choice_expired"}

        mode = str(context.payload.get("mode") or "").strip().lower()
        if mode not in {"remote", "onsite", "hybrid"}:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Неизвестный режим работы",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_work_modes_choice_invalid"}

        payload = dict(state.payload) if isinstance(state.payload, dict) else {}
        selected = self._extract_selected_work_modes_payload(payload)
        if mode in selected:
            selected = [item for item in selected if item != mode]
        else:
            selected.append(mode)
        payload["selected_work_modes"] = selected

        await self._conversation_state_service.set_state(
            telegram_user_id=actor.id,
            role_context=ROLE_CANDIDATE,
            state_key=state.state_key,
            payload=payload,
        )
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Выбор обновлён",
            show_alert=False,
        )
        is_registration = state.state_key == STATE_CANDIDATE_REG_WORK_MODES
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_structured_prompt(
                section_path=(
                    "Регистрация кандидата"
                    if is_registration
                    else "Кабинет кандидата · Редактирование"
                ),
                title="Выбери форматы работы",
                instruction="Используй кнопки ниже, чтобы отметить подходящие варианты.",
                current_value=self._format_work_modes_choice_for_prompt(payload),
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_work_modes_selector_markup(
                telegram_user_id=actor.id,
                selected_modes=selected,
                allow_clear=not is_registration,
            ),
        )
        return {"status": "processed", "action": "candidate_work_modes_choice_toggled"}

    async def _handle_candidate_choice_work_modes_done(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key not in {
            STATE_CANDIDATE_REG_WORK_MODES,
            STATE_CANDIDATE_EDIT_WORK_MODES,
        }:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Шаг выбора формата работы устарел.",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_work_modes_done_expired"}

        payload = dict(state.payload) if isinstance(state.payload, dict) else {}
        selected = self._extract_selected_work_modes_payload(payload)

        if state.state_key == STATE_CANDIDATE_REG_WORK_MODES:
            if not selected:
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Выбери минимум один формат работы",
                    show_alert=True,
                )
                return {"status": "processed", "action": "candidate_registration_work_modes_empty"}
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_CONTACTS_VISIBILITY,
                payload={"work_modes": selected},
            )
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Формат работы сохранен",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=self._build_structured_prompt(
                    section_path="Регистрация кандидата",
                    title="Выбери видимость контактов",
                    instruction="Используй кнопки ниже, чтобы задать режим приватности.",
                    current_value="—",
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_candidate_contacts_visibility_selector_markup(
                    telegram_user_id=actor.id,
                    selected_visibility=None,
                ),
            )
            return {"status": "processed", "action": "candidate_registration_work_modes_saved"}

        return await self._submit_candidate_choice_edit_from_callback(
            callback=callback,
            actor=actor,
            callback_text="Сохраняю формат работы",
            field_name="work_modes",
            raw_value=selected,
        )

    async def _handle_candidate_choice_work_modes_clear(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key != STATE_CANDIDATE_EDIT_WORK_MODES:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Шаг редактирования устарел",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_edit_work_modes_clear_expired"}
        payload = dict(state.payload) if isinstance(state.payload, dict) else {}
        payload["selected_work_modes"] = []
        await self._conversation_state_service.set_state(
            telegram_user_id=actor.id,
            role_context=ROLE_CANDIDATE,
            state_key=STATE_CANDIDATE_EDIT_WORK_MODES,
            payload=payload,
        )
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Выбор очищен",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_structured_prompt(
                section_path="Кабинет кандидата · Редактирование",
                title="Выбери форматы работы",
                instruction="Используй кнопки ниже, чтобы отметить подходящие варианты.",
                current_value="—",
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_work_modes_selector_markup(
                telegram_user_id=actor.id,
                selected_modes=[],
                allow_clear=True,
            ),
        )
        return {"status": "processed", "action": "candidate_edit_work_modes_cleared"}

    async def _handle_candidate_choice_contacts_visibility(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key not in {
            STATE_CANDIDATE_REG_CONTACTS_VISIBILITY,
            STATE_CANDIDATE_EDIT_CONTACTS_VISIBILITY,
        }:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Шаг выбора видимости устарел.",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_visibility_choice_expired"}

        value = str(context.payload.get("value") or "").strip().lower()
        if value not in {
            CONTACT_VISIBILITY_PUBLIC,
            CONTACT_VISIBILITY_ON_REQUEST,
            CONTACT_VISIBILITY_HIDDEN,
        }:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Недопустимое значение",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_visibility_choice_invalid"}

        if state.state_key == STATE_CANDIDATE_REG_CONTACTS_VISIBILITY:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            work_modes = self._extract_selected_work_modes_payload(payload)
            if not work_modes:
                await self._conversation_state_service.set_state(
                    telegram_user_id=actor.id,
                    role_context=ROLE_CANDIDATE,
                    state_key=STATE_CANDIDATE_REG_WORK_MODES,
                    payload={"selected_work_modes": []},
                )
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Верну к выбору формата работы",
                    show_alert=False,
                )
                await self._render_callback_screen(
                    callback=callback,
                    actor=actor,
                    text=self._build_structured_prompt(
                        section_path="Регистрация кандидата",
                        title="Выбери форматы работы",
                        instruction="Используй кнопки ниже, чтобы отметить подходящие варианты.",
                        current_value="—",
                    ),
                    parse_mode="Markdown",
                    reply_markup=await self._build_candidate_work_modes_selector_markup(
                        telegram_user_id=actor.id,
                        selected_modes=[],
                        allow_clear=False,
                    ),
                )
                return {"status": "processed", "action": "candidate_registration_work_modes_reset"}
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_ENGLISH_LEVEL,
                payload={
                    "work_modes": work_modes,
                    "contacts_visibility": value,
                },
            )
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Видимость контактов сохранена",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=self._build_structured_prompt(
                    section_path="Регистрация кандидата",
                    title="Выбери уровень английского",
                    instruction="Используй кнопки ниже, чтобы указать актуальный уровень.",
                    current_value="—",
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_candidate_english_level_selector_markup(
                    telegram_user_id=actor.id,
                    selected_level=None,
                    allow_clear=True,
                ),
            )
            return {
                "status": "processed",
                "action": "candidate_registration_contacts_visibility_saved",
            }

        return await self._submit_candidate_choice_edit_from_callback(
            callback=callback,
            actor=actor,
            callback_text="Сохраняю видимость контактов",
            field_name="contacts_visibility",
            raw_value=value,
        )

    async def _handle_candidate_choice_english_level(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key not in {
            STATE_CANDIDATE_REG_ENGLISH_LEVEL,
            STATE_CANDIDATE_EDIT_ENGLISH_LEVEL,
        }:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Шаг выбора английского устарел.",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_english_choice_expired"}

        raw = str(context.payload.get("value") or "").strip().upper()
        english_level = raw or None
        if english_level is not None and english_level not in {"A1", "A2", "B1", "B2", "C1", "C2"}:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Недопустимый уровень английского",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_english_choice_invalid"}

        if state.state_key == STATE_CANDIDATE_REG_ENGLISH_LEVEL:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["english_level"] = english_level
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_SALARY,
                payload=payload,
            )
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Английский сохранен",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=self._build_structured_prompt(
                    section_path="Регистрация кандидата",
                    title="Укажи зарплату",
                    instruction="Можно указать диапазон, только минимум или только максимум.",
                    examples=["250000 350000 RUB", "от 250000 RUB", "до 350000 RUB"],
                    footer="Чтобы пропустить шаг, отправь `-`.",
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "candidate_registration_english_saved"}

        return await self._submit_candidate_choice_edit_from_callback(
            callback=callback,
            actor=actor,
            callback_text="Сохраняю уровень английского",
            field_name="english_level",
            raw_value=english_level,
        )

    async def _handle_candidate_choice_status(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is None or state.state_key != STATE_CANDIDATE_EDIT_STATUS:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Шаг выбора статуса устарел.",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_status_choice_expired"}

        value = str(context.payload.get("value") or "").strip().lower()
        if value not in {"active", "hidden"}:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Недопустимый статус",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_status_choice_invalid"}

        return await self._submit_candidate_choice_edit_from_callback(
            callback=callback,
            actor=actor,
            callback_text="Сохраняю статус",
            field_name="status",
            raw_value=value,
        )

    async def _submit_candidate_choice_edit_from_callback(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        callback_text: str,
        field_name: str,
        raw_value: object | None,
    ) -> dict:
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text=callback_text,
            show_alert=False,
        )
        return await self._handle_candidate_edit_submit(
            actor=actor,
            chat_id=self._resolve_chat_id(callback, actor),
            field_name=field_name,
            raw_value=raw_value,
        )

    def _extract_selected_work_modes_payload(self, payload: dict | None) -> list[str]:
        if not isinstance(payload, dict):
            return []
        source = payload.get("selected_work_modes")
        if not isinstance(source, list):
            source = payload.get("work_modes")
        if not isinstance(source, list):
            return []
        result: list[str] = []
        for item in source:
            mode = str(item).strip().lower()
            if mode not in {"remote", "onsite", "hybrid"}:
                continue
            if mode not in result:
                result.append(mode)
        return result

    def _extract_selected_contacts_visibility_payload(self, payload: dict | None) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get("selected_contacts_visibility")
        if value is None:
            value = payload.get("contacts_visibility")
        normalized = str(value or "").strip().lower()
        if normalized in {
            CONTACT_VISIBILITY_PUBLIC,
            CONTACT_VISIBILITY_ON_REQUEST,
            CONTACT_VISIBILITY_HIDDEN,
        }:
            return normalized
        return None

    def _extract_selected_english_level_payload(self, payload: dict | None) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get("selected_english_level")
        if value is None:
            value = payload.get("english_level")
        normalized = str(value or "").strip().upper()
        if normalized in {"A1", "A2", "B1", "B2", "C1", "C2"}:
            return normalized
        return None

    def _extract_selected_candidate_status_payload(self, payload: dict | None) -> str | None:
        if not isinstance(payload, dict):
            return None
        value = str(payload.get("selected_status") or payload.get("status") or "").strip().lower()
        if value in {"active", "hidden"}:
            return value
        return None

    def _format_work_modes_choice_for_prompt(self, payload: dict | None) -> str:
        selected = self._extract_selected_work_modes_payload(payload)
        if not selected:
            return "—"
        return ", ".join(self._humanize_work_mode(item) for item in selected)

    def _format_contacts_visibility_for_prompt(self, payload: dict | None) -> str:
        selected = self._extract_selected_contacts_visibility_payload(payload)
        return self._humanize_contacts_visibility_for_profile(selected)

    def _format_english_level_for_prompt(self, payload: dict | None) -> str:
        selected = self._extract_selected_english_level_payload(payload)
        return selected or "—"

    def _format_candidate_status_for_prompt(self, payload: dict | None) -> str:
        selected = self._extract_selected_candidate_status_payload(payload)
        return self._humanize_candidate_status(selected)
