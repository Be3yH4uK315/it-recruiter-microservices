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
            await self._telegram_client.send_message(
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
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=error_text,
                )
                return {"status": "processed", "action": "candidate_registration_display_name_invalid"}
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_HEADLINE_ROLE,
                payload={"display_name": display_name},
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Теперь укажи основную роль в поиске, например: Python Developer.",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_registration_display_name_saved"}

        if state.state_key == STATE_CANDIDATE_REG_HEADLINE_ROLE:
            display_name = self._extract_payload_text(state.payload, "display_name")
            if not display_name:
                await self._conversation_state_service.set_state(
                    telegram_user_id=actor.id,
                    role_context=ROLE_CANDIDATE,
                    state_key=STATE_CANDIDATE_REG_DISPLAY_NAME,
                    payload=None,
                )
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=(
                        "Состояние регистрации сброшено. "
                        "Введи отображаемое имя кандидата ещё раз."
                    ),
                )
                return {"status": "processed", "action": "candidate_registration_reset"}

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

            stats = await self._safe_get_candidate_statistics(
                access_token=access_token,
                candidate_id=candidate.id,
            )

            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    self._build_candidate_dashboard_message(
                        first_name=actor.first_name,
                        candidate=candidate,
                        statistics=stats,
                        created_now=True,
                    )
                    + "\n\n"
                    + "Базовая регистрация завершена.\n"
                    + "Хочешь продолжить и заполнить дополнительные поля профиля?"
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_candidate_registration_continue_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_registered_minimal"}

        if state.state_key == STATE_CANDIDATE_REG_WORK_MODES:
            await self._telegram_client.send_message(
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
            await self._telegram_client.send_message(
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
            await self._telegram_client.send_message(
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
                await self._telegram_client.send_message(
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
                    await self._telegram_client.send_message(
                        chat_id=chat_id,
                        text="Формат зарплаты: `min max currency`, например `250000 350000 RUB`.",
                        parse_mode="Markdown",
                    )
                    return {
                        "status": "processed",
                        "action": "candidate_registration_salary_invalid",
                    }
                salary_min, salary_max, currency = parsed_salary
                if salary_min < 0 or salary_max < 0 or salary_max < salary_min:
                    await self._telegram_client.send_message(
                        chat_id=chat_id,
                        text="Проверь значения: min/max >= 0 и max >= min.",
                    )
                    return {
                        "status": "processed",
                        "action": "candidate_registration_salary_invalid",
                    }
                if currency is not None and (len(currency) < 3 or len(currency) > 5):
                    await self._telegram_client.send_message(
                        chat_id=chat_id,
                        text="Валюта должна быть кодом вроде RUB, USD, EUR.",
                    )
                    return {
                        "status": "processed",
                        "action": "candidate_registration_salary_invalid",
                    }
            payload["work_modes"] = work_modes
            payload["contacts_visibility"] = contacts_visibility
            payload["english_level"] = english_level
            payload["salary_min"] = salary_min
            payload["salary_max"] = salary_max
            payload["currency"] = currency
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_LOCATION,
                payload=payload,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "Полная регистрация кандидата\n\n"
                    "Укажи локацию (город/страна) или `-`, чтобы пропустить."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_registration_salary_saved"}

        if state.state_key == STATE_CANDIDATE_REG_LOCATION:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["location"] = self._normalize_optional_user_input(text)
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_ABOUT_ME,
                payload=payload,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "Полная регистрация кандидата\n\n"
                    "Напиши кратко о себе или отправь `-`, чтобы пропустить."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_registration_location_saved"}

        if state.state_key == STATE_CANDIDATE_REG_ABOUT_ME:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["about_me"] = self._normalize_optional_user_input(text)
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_CONTACT_EMAIL,
                payload=payload,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "Полная регистрация кандидата\n\n"
                    "Укажи email или отправь `-`, чтобы пропустить."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_registration_about_saved"}

        if state.state_key == STATE_CANDIDATE_REG_CONTACT_EMAIL:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            value = self._normalize_optional_user_input(text)
            if value is not None:
                value, error_text = self._normalize_contact_value(
                    contact_key="email",
                    raw_value=value,
                )
                if error_text is not None:
                    await self._telegram_client.send_message(
                        chat_id=chat_id,
                        text=error_text,
                        parse_mode="Markdown",
                    )
                    return {
                        "status": "processed",
                        "action": "candidate_registration_contact_email_invalid",
                    }
            payload["contact_email"] = value
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_CONTACT_PHONE,
                payload=payload,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "Полная регистрация кандидата\n\n"
                    "Укажи телефон или отправь `-`, чтобы пропустить."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_registration_contact_email_saved"}

        if state.state_key == STATE_CANDIDATE_REG_CONTACT_PHONE:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            value = self._normalize_optional_user_input(text)
            if value is not None:
                value, error_text = self._normalize_contact_value(
                    contact_key="phone",
                    raw_value=value,
                )
                if error_text is not None:
                    await self._telegram_client.send_message(
                        chat_id=chat_id,
                        text=error_text,
                        parse_mode="Markdown",
                    )
                    return {
                        "status": "processed",
                        "action": "candidate_registration_contact_phone_invalid",
                    }
            payload["contact_phone"] = value
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_SKILLS,
                payload=payload,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "Полная регистрация кандидата\n\n"
                    "Введи навыки, по одному на строку:\n"
                    "`skill; kind; level`\n"
                    "Разделитель: `;` (также поддерживается `|`).\n"
                    "kind: `hard`, `soft`, `tool`, `language`.\n"
                    "level: 1..5 (можно пусто).\n"
                    "Пример: `Python; hard; 5`\n"
                    "Чтобы пропустить, отправь `-`."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_registration_contact_phone_saved"}

        if state.state_key == STATE_CANDIDATE_REG_SKILLS:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed_skills, error_text = self._parse_candidate_registration_skills(text)
            if error_text is not None:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=error_text,
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_registration_skills_invalid"}
            payload["skills"] = parsed_skills
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_EDUCATION,
                payload=payload,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "Полная регистрация кандидата\n\n"
                    "Введи образование, по одному на строку:\n"
                    "`level; institution; year`\n"
                    "Разделитель: `;` (также поддерживается `|`).\n"
                    "Пример: `Bachelor; NSU; 2022`\n"
                    "Чтобы пропустить, отправь `-`."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_registration_skills_saved"}

        if state.state_key == STATE_CANDIDATE_REG_EDUCATION:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed_education, error_text = self._parse_candidate_registration_education(text)
            if error_text is not None:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=error_text,
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_registration_education_invalid"}
            payload["education"] = parsed_education
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_EXPERIENCES,
                payload=payload,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "Полная регистрация кандидата\n\n"
                    "Введи опыт, по одному на строку:\n"
                    "`company; position; start_date; end_date; responsibilities`\n"
                    "Разделитель: `;` (также поддерживается `|`).\n"
                    "Дата: `YYYY-MM-DD`, `end_date` можно пустым.\n"
                    "Пример: `Acme; Backend Developer; 2023-01-01; "
                    "2024-02-01; FastAPI и PostgreSQL`\n"
                    "Чтобы пропустить, отправь `-`."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_registration_education_saved"}

        if state.state_key == STATE_CANDIDATE_REG_EXPERIENCES:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed_experiences, error_text = self._parse_candidate_registration_experiences(text)
            if error_text is not None:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=error_text,
                    parse_mode="Markdown",
                )
                return {
                    "status": "processed",
                    "action": "candidate_registration_experiences_invalid",
                }
            payload["experiences"] = parsed_experiences
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_REG_PROJECTS,
                payload=payload,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "Полная регистрация кандидата\n\n"
                    "Введи проекты, по одному на строку:\n"
                    "`title; description; link1,link2`\n"
                    "Разделитель между полями: `;` (также поддерживается `|`).\n"
                    "Ссылки опциональны, только http/https.\n"
                    "Пример: `ATS Bot; Telegram recruiting bot; https://github.com/org/repo`\n"
                    "Чтобы пропустить, отправь `-`."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_registration_experiences_saved"}

        if state.state_key == STATE_CANDIDATE_REG_PROJECTS:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed_projects, error_text = self._parse_candidate_registration_projects(text)
            if error_text is not None:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=error_text,
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "candidate_registration_projects_invalid"}
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
            await self._telegram_client.send_message(
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
            await self._telegram_client.send_message(
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
            await self._telegram_client.send_message(
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
            await self._telegram_client.send_message(
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
                    await self._telegram_client.send_message(
                        chat_id=chat_id,
                        text=error_text,
                    )
                    return {
                        "status": "processed",
                        "action": "employer_registration_company_invalid",
                    }
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

            stats = await self._safe_get_employer_statistics(
                access_token=access_token,
                employer_id=employer.id,
            )

            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    self._build_employer_dashboard_message(
                        first_name=actor.first_name,
                        employer=employer,
                        statistics=stats,
                        created_now=True,
                    )
                    + "\n\n"
                    + "Базовая регистрация завершена.\n"
                    + "Хочешь продолжить и заполнить дополнительные поля профиля?"
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_employer_registration_continue_markup(actor.id),
            )
            return {"status": "processed", "action": "employer_registered_minimal"}

        if state.state_key == STATE_EMPLOYER_REG_CONTACT_TELEGRAM:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["telegram"] = self._build_telegram_contact(actor)
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_REG_CONTACT_EMAIL,
                payload=payload,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "Telegram-контакт компании синхронизирован автоматически.\n"
                    "Введи `email` компании или отправь `-`, чтобы пропустить."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "employer_registration_contact_telegram_saved"}

        if state.state_key == STATE_EMPLOYER_REG_CONTACT_EMAIL:
            value = self._normalize_optional_user_input(text)
            if value is not None:
                value, error_text = self._normalize_contact_value(
                    contact_key="email",
                    raw_value=value,
                )
                if error_text is not None:
                    await self._telegram_client.send_message(
                        chat_id=chat_id,
                        text=error_text,
                        parse_mode="Markdown",
                    )
                    return {
                        "status": "processed",
                        "action": "employer_registration_contact_email_invalid",
                    }
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["email"] = value or None
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_REG_CONTACT_PHONE,
                payload=payload,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Введи `phone` компании или отправь `-`, чтобы пропустить.",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "employer_registration_contact_email_saved"}

        if state.state_key == STATE_EMPLOYER_REG_CONTACT_PHONE:
            value = self._normalize_optional_user_input(text)
            if value is not None:
                value, error_text = self._normalize_contact_value(
                    contact_key="phone",
                    raw_value=value,
                )
                if error_text is not None:
                    await self._telegram_client.send_message(
                        chat_id=chat_id,
                        text=error_text,
                        parse_mode="Markdown",
                    )
                    return {
                        "status": "processed",
                        "action": "employer_registration_contact_phone_invalid",
                    }
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["phone"] = value or None
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_REG_CONTACT_WEBSITE,
                payload=payload,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Введи `website` компании или отправь `-`, чтобы пропустить.",
                parse_mode="Markdown",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "employer_registration_contact_phone_saved"}

        if state.state_key == STATE_EMPLOYER_REG_CONTACT_WEBSITE:
            value = self._normalize_optional_user_input(text)
            if value is not None:
                value, error_text = self._normalize_contact_value(
                    contact_key="website",
                    raw_value=value,
                )
                if error_text is not None:
                    await self._telegram_client.send_message(
                        chat_id=chat_id,
                        text=error_text,
                        parse_mode="Markdown",
                    )
                    return {
                        "status": "processed",
                        "action": "employer_registration_contact_website_invalid",
                    }
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
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=(
                        "Название должно быть не короче "
                        f"{EMPLOYER_SEARCH_TITLE_MIN_LEN} символов."
                    ),
                )
                return {"status": "processed", "action": "employer_search_title_invalid"}
            if len(title) > EMPLOYER_SEARCH_TITLE_MAX_LEN:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=(
                        "Название слишком длинное. Максимум "
                        f"{EMPLOYER_SEARCH_TITLE_MAX_LEN} символов."
                    ),
                )
                return {"status": "processed", "action": "employer_search_title_too_long"}

            payload["title"] = title
            if self._is_employer_search_edit_step(payload, step="title"):
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {"status": "processed", "action": "employer_search_title_saved_from_confirm"}
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_SEARCH_ROLE,
                payload=payload,
                chat_id=chat_id,
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Теперь введи основную роль для поиска. Например: Python Backend Developer."
                ),
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step="role",
                    allow_skip=False,
                ),
            )
            return {"status": "processed", "action": "employer_search_title_saved"}

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
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Роль должна быть не короче {EMPLOYER_SEARCH_ROLE_MIN_LEN} символов.",
                )
                return {"status": "processed", "action": "employer_search_role_invalid"}
            if len(role) > EMPLOYER_SEARCH_ROLE_MAX_LEN:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=f"Роль слишком длинная. Максимум {EMPLOYER_SEARCH_ROLE_MAX_LEN} символов.",
                )
                return {"status": "processed", "action": "employer_search_role_too_long"}

            payload["role"] = role
            if self._is_employer_search_edit_step(payload, step="role"):
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {"status": "processed", "action": "employer_search_role_saved_from_confirm"}
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_SEARCH_MUST_SKILLS,
                payload=payload,
                chat_id=chat_id,
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Введи обязательные навыки через запятую.\n"
                    "Можно указать уровень: `Python:4, FastAPI:3`.\n"
                    "Отправь `-`, если шаг пропускаем."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step="must_skills",
                    allow_skip=True,
                ),
            )
            return {"status": "processed", "action": "employer_search_role_saved"}

        if state.state_key == STATE_EMPLOYER_SEARCH_MUST_SKILLS:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed = self._parse_search_skill_list(text)
            if parsed is None:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text="Неверный формат навыков. Пример: `Python:4, FastAPI:3` или `-`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "employer_search_must_skills_invalid"}
            payload["must_skills"] = parsed
            if self._is_employer_search_edit_step(payload, step="must_skills"):
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_must_skills_saved_from_confirm",
                }
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_SEARCH_NICE_SKILLS,
                payload=payload,
                chat_id=chat_id,
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Введи желательные навыки через запятую.\n"
                    "Пример: `Docker:3, AWS`.\n"
                    "Отправь `-`, если шаг пропускаем."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step="nice_skills",
                    allow_skip=True,
                ),
            )
            return {"status": "processed", "action": "employer_search_must_skills_saved"}

        if state.state_key == STATE_EMPLOYER_SEARCH_NICE_SKILLS:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            parsed = self._parse_search_skill_list(text)
            if parsed is None:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text="Неверный формат навыков. Пример: `Docker:3, AWS` или `-`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "employer_search_nice_skills_invalid"}
            payload["nice_skills"] = parsed
            if self._is_employer_search_edit_step(payload, step="nice_skills"):
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_nice_skills_saved_from_confirm",
                }
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_SEARCH_EXPERIENCE,
                payload=payload,
                chat_id=chat_id,
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Диапазон опыта в формате `min-max`, например `2-5`. "
                    "Отправь `-`, чтобы пропустить."
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step="experience",
                    allow_skip=True,
                ),
            )
            return {"status": "processed", "action": "employer_search_nice_skills_saved"}

        if state.state_key == STATE_EMPLOYER_SEARCH_EXPERIENCE:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            experience = self._parse_search_experience_range(text)
            if experience is None:
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text="Неверный формат опыта. Используй `min-max` (например `2-5`) или `-`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "employer_search_experience_invalid"}
            payload["experience_min"] = experience[0]
            payload["experience_max"] = experience[1]
            if self._is_employer_search_edit_step(payload, step="experience"):
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_experience_saved_from_confirm",
                }
            await self._set_state_and_render_wizard_step(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_SEARCH_LOCATION,
                payload=payload,
                chat_id=chat_id,
                text=(
                    "Кабинет работодателя > Поиск > Новый поиск\n\n🧭 Мастер поиска\n\n"
                    "Введи желаемую локацию (город/страна) или `-`, чтобы пропустить."
                ),
                reply_markup=await self._build_employer_search_wizard_controls_markup(
                    telegram_user_id=actor.id,
                    step="location",
                    allow_skip=True,
                ),
            )
            return {"status": "processed", "action": "employer_search_experience_saved"}

        if state.state_key == STATE_EMPLOYER_SEARCH_LOCATION:
            payload = dict(state.payload) if isinstance(state.payload, dict) else {}
            payload["location"] = self._normalize_optional_user_input(text)
            if self._is_employer_search_edit_step(payload, step="location"):
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_location_saved_from_confirm",
                }
            await self._render_employer_search_work_modes_step(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                payload=payload,
                allow_skip=True,
            )
            return {"status": "processed", "action": "employer_search_location_saved"}

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
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text="Неверный формат зарплаты. Пример: `150000 250000 RUB` или `-`.",
                    parse_mode="Markdown",
                )
                return {"status": "processed", "action": "employer_search_salary_invalid"}
            payload["salary_min"] = salary[0]
            payload["salary_max"] = salary[1]
            payload["currency"] = salary[2]
            if self._is_employer_search_edit_step(payload, step="salary"):
                await self._render_employer_search_confirm_step(
                    telegram_user_id=actor.id,
                    chat_id=chat_id,
                    payload=payload,
                )
                return {
                    "status": "processed",
                    "action": "employer_search_salary_saved_from_confirm",
                }
            await self._render_employer_search_english_step(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                payload=payload,
                allow_skip=True,
            )
            return {"status": "processed", "action": "employer_search_salary_saved"}

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
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text=(
                        "Описание слишком длинное. Максимум "
                        f"{EMPLOYER_SEARCH_ABOUT_MAX_LEN} символов."
                    ),
                )
                return {"status": "processed", "action": "employer_search_about_too_long"}
            payload["about_me"] = normalized_about
            await self._render_employer_search_confirm_step(
                telegram_user_id=actor.id,
                chat_id=chat_id,
                payload=payload,
            )
            return {"status": "processed", "action": "employer_search_about_saved"}

        await self._telegram_client.send_message(
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
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сессия устарела. Нажми /start, чтобы выбрать роль заново.",
            )
            return {"status": "processed", "action": "session_expired"}

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
                await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
                await self._telegram_client.send_message(
                    chat_id=chat_id,
                    text="Профиль кандидата не найден. Нажми /start, чтобы начать заново.",
                )
                return {"status": "processed", "action": "candidate_not_found"}

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
        stats = await self._safe_get_candidate_statistics(
            access_token=access_token,
            candidate_id=updated.id,
        )
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=self._build_candidate_dashboard_message(
                first_name=actor.first_name,
                candidate=updated,
                statistics=stats,
                created_now=False,
            ),
            parse_mode="Markdown",
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
            text=(
                "Регистрация кандидата\n\n"
                "Выбери форматы работы кнопками ниже.\n\n"
                f"Текущий выбор: {self._format_work_modes_choice_for_prompt(payload)}"
                if is_registration
                else "Кабинет кандидата > Редактирование\n\n"
                "✏️ Редактирование\n\n"
                "Выбери форматы работы кнопками ниже.\n\n"
                f"Текущий выбор: {self._format_work_modes_choice_for_prompt(payload)}"
            ),
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
                text=("Регистрация кандидата\n\n" "Теперь выбери видимость контактов."),
                reply_markup=await self._build_candidate_contacts_visibility_selector_markup(
                    telegram_user_id=actor.id,
                    selected_visibility=None,
                ),
            )
            return {"status": "processed", "action": "candidate_registration_work_modes_saved"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Сохраняю формат работы",
            show_alert=False,
        )
        await self._telegram_client.send_message(
            chat_id=self._resolve_chat_id(callback, actor),
            text=f"Текущий выбор: {self._format_work_modes_choice_for_prompt(payload)}",
        )
        return await self._handle_candidate_edit_submit(
            actor=actor,
            chat_id=self._resolve_chat_id(callback, actor),
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
            text=(
                "Кабинет кандидата > Редактирование\n\n"
                "✏️ Редактирование\n\n"
                "Выбери форматы работы кнопками ниже.\n\n"
                "Текущий выбор: —"
            ),
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
                    text=(
                        "Регистрация кандидата\n\n"
                        "Выбери форматы работы кнопками ниже.\n\n"
                        "Текущий выбор: —"
                    ),
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
                text=("Регистрация кандидата\n\n" "Выбери уровень английского."),
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

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Сохраняю видимость контактов",
            show_alert=False,
        )
        await self._telegram_client.send_message(
            chat_id=self._resolve_chat_id(callback, actor),
            text=f"Текущий выбор: {self._humanize_contacts_visibility_for_profile(value)}",
        )
        return await self._handle_candidate_edit_submit(
            actor=actor,
            chat_id=self._resolve_chat_id(callback, actor),
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
                text=(
                    "Регистрация кандидата\n\n"
                    "Укажи зарплату в формате: `min max currency`.\n"
                    "Пример: `250000 350000 RUB`.\n"
                    "Чтобы пропустить, отправь `-`."
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "candidate_registration_english_saved"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Сохраняю уровень английского",
            show_alert=False,
        )
        await self._telegram_client.send_message(
            chat_id=self._resolve_chat_id(callback, actor),
            text=f"Текущий выбор: {english_level or '—'}",
        )
        return await self._handle_candidate_edit_submit(
            actor=actor,
            chat_id=self._resolve_chat_id(callback, actor),
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

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Сохраняю статус",
            show_alert=False,
        )
        await self._telegram_client.send_message(
            chat_id=self._resolve_chat_id(callback, actor),
            text=f"Текущий выбор: {self._humanize_candidate_status(value)}",
        )
        return await self._handle_candidate_edit_submit(
            actor=actor,
            chat_id=self._resolve_chat_id(callback, actor),
            field_name="status",
            raw_value=value,
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
