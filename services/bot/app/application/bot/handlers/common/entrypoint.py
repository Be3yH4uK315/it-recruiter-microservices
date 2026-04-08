from __future__ import annotations

from app.application.bot.constants import (
    ROLE_CANDIDATE,
    ROLE_EMPLOYER,
    STATE_CANDIDATE_EDIT_ABOUT_ME,
    STATE_CANDIDATE_EDIT_CONTACT_EMAIL,
    STATE_CANDIDATE_EDIT_CONTACT_PHONE,
    STATE_CANDIDATE_EDIT_DISPLAY_NAME,
    STATE_CANDIDATE_EDIT_EDUCATION,
    STATE_CANDIDATE_EDIT_EXPERIENCES,
    STATE_CANDIDATE_EDIT_HEADLINE_ROLE,
    STATE_CANDIDATE_EDIT_LOCATION,
    STATE_CANDIDATE_EDIT_PROJECTS,
    STATE_CANDIDATE_EDIT_SALARY,
    STATE_CANDIDATE_EDIT_SKILLS,
    STATE_CANDIDATE_FILE_AWAIT_AVATAR,
    STATE_CANDIDATE_FILE_AWAIT_RESUME,
    STATE_EMPLOYER_EDIT_COMPANY,
    STATE_EMPLOYER_EDIT_CONTACT_EMAIL,
    STATE_EMPLOYER_EDIT_CONTACT_PHONE,
    STATE_EMPLOYER_EDIT_CONTACT_WEBSITE,
    STATE_EMPLOYER_FILE_AWAIT_AVATAR,
    STATE_EMPLOYER_FILE_AWAIT_DOCUMENT,
)
from app.application.observability.metrics import mark_callback_failed
from app.schemas.telegram import TelegramCallbackQuery, TelegramMessage


class EntrypointHandlersMixin:
    async def _handle_message(self, message: TelegramMessage) -> dict:
        actor = message.from_user
        if actor is None or message.chat is None:
            return {"status": "ignored", "reason": "message_without_actor_or_chat"}
        self._log_flow_event(
            "message_received",
            telegram_user_id=actor.id,
            extra={"message_id": message.message_id, "has_text": bool(message.text)},
        )

        rate_limit = self._rate_limit_service.check_message(telegram_user_id=actor.id)
        if not rate_limit.allowed:
            await self._telegram_client.send_message(
                chat_id=message.chat.id,
                text="Слишком часто. Попробуй чуть позже.",
            )
            return {"status": "processed", "action": "message_rate_limited"}

        text = (message.text or "").strip()

        if text == "/start":
            state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
            if state is not None and state.state_key:
                state_label = self._build_draft_conflict_state_label(state.state_key)
                await self._telegram_client.send_message(
                    chat_id=message.chat.id,
                    text=(
                        "Нашли незавершённое действие.\n\n"
                        f"Текущий шаг: {state_label}\n\n"
                        "Хочешь продолжить с места остановки?"
                    ),
                    reply_markup=await self._build_start_resume_draft_markup(
                        telegram_user_id=actor.id
                    ),
                )
                return {"status": "processed", "action": "start_with_draft_prompt"}
            await self._send_role_selection(chat_id=message.chat.id, actor=actor)
            return {"status": "processed", "action": "start"}

        if text == "/logout":
            await self._auth_session_service.logout(telegram_user_id=actor.id)
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=message.chat.id,
                text="Сессия завершена. Нажми /start, чтобы выбрать роль заново.",
            )
            return {"status": "processed", "action": "logout"}

        if text == "/cancel":
            return await self._handle_cancel_command(message=message, actor=actor)

        if text == "/help":
            return await self._handle_help_command(message=message, actor=actor)

        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        if state is not None and state.state_key is not None:
            return await self._handle_stateful_message(
                message=message,
                actor=actor,
                state=state,
            )

        await self._telegram_client.send_message(
            chat_id=message.chat.id,
            text=(
                "Поддерживаемые команды: /start, /logout, /cancel, /help.\n"
                "Для работы с меню нажми /start."
            ),
        )
        return {"status": "processed", "action": "fallback_message"}

    async def _handle_callback(self, callback: TelegramCallbackQuery) -> dict:
        actor = callback.from_user
        if actor is None:
            return {"status": "ignored", "reason": "callback_without_actor"}

        rate_limit = self._rate_limit_service.check_callback(telegram_user_id=actor.id)
        if not rate_limit.allowed:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Слишком часто. Попробуй чуть позже.",
                show_alert=False,
            )
            return {"status": "processed", "action": "callback_rate_limited"}

        if not callback.data:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Кнопка без данных",
                show_alert=False,
            )
            return {"status": "ignored", "reason": "empty_callback_data"}

        context = await self._resolve_and_consume_callback_context(
            callback_data=callback.data,
            telegram_user_id=actor.id,
        )
        if context is None:
            mark_callback_failed("expired_context")
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Кнопка устарела. Нажми /start, чтобы открыть меню заново.",
                show_alert=True,
            )
            return {"status": "processed", "action": "expired_callback"}

        action = context.action_type
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        self._log_flow_event(
            "callback_received",
            telegram_user_id=actor.id,
            action_type=action,
            role_context=state.role_context if state is not None else None,
            state_key=state.state_key if state is not None else None,
            extra={"callback_id": callback.id},
        )

        if action == "draft_conflict_continue":
            return await self._handle_draft_conflict_continue(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "draft_conflict_reset_and_go":
            return await self._handle_draft_conflict_reset_and_go(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "start_resume_continue":
            return await self._handle_start_resume_continue(
                callback=callback,
                actor=actor,
            )

        if action == "start_resume_reset":
            return await self._handle_start_resume_reset(
                callback=callback,
                actor=actor,
            )

        if self._should_prompt_draft_conflict(
            state=state,
            action=action,
        ):
            return await self._handle_draft_conflict_prompt(
                callback=callback,
                actor=actor,
                state=state,
                target_action=action,
                target_payload=context.payload,
            )

        if action == "select_role":
            return await self._handle_select_role_callback(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "candidate_menu_dashboard":
            return await self._handle_candidate_dashboard(callback=callback, actor=actor)

        if action == "candidate_menu_profile":
            return await self._handle_candidate_profile(callback=callback, actor=actor)

        if action == "candidate_menu_profile_edit_menu":
            return await self._handle_candidate_profile_edit_menu(callback=callback, actor=actor)

        if action == "candidate_menu_stats":
            return await self._handle_candidate_stats(callback=callback, actor=actor)

        if action == "candidate_menu_help":
            return await self._handle_candidate_help(callback=callback, actor=actor)

        if action == "candidate_menu_open_edit_section":
            return await self._handle_candidate_profile_edit_menu(callback=callback, actor=actor)

        if action == "candidate_edit_cancel":
            return await self._handle_candidate_edit_cancel(callback=callback, actor=actor)

        if action == "stateful_input_cancel":
            return await self._handle_stateful_input_cancel(callback=callback, actor=actor)

        if action == "candidate_menu_open_files_section":
            return await self._handle_candidate_open_files_section(
                callback=callback,
                actor=actor,
            )

        if action == "candidate_menu_open_contacts_section":
            return await self._handle_candidate_open_contacts_section(
                callback=callback,
                actor=actor,
            )

        if action == "candidate_menu_switch_role":
            return await self._handle_switch_role_from_menu(callback=callback, actor=actor)

        if action == "candidate_menu_edit_display_name":
            return await self._handle_candidate_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_CANDIDATE_EDIT_DISPLAY_NAME,
                prompt=self._build_profile_name_prompt(
                    field_label="отображаемое имя кандидата",
                    example="Иван Петров",
                ),
                action_name="candidate_edit_display_name_start",
            )

        if action == "candidate_menu_edit_headline_role":
            return await self._handle_candidate_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_CANDIDATE_EDIT_HEADLINE_ROLE,
                prompt="Введи основную роль кандидата. Например: Python Developer.",
                action_name="candidate_edit_headline_role_start",
            )

        if action == "candidate_menu_edit_location":
            return await self._handle_candidate_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_CANDIDATE_EDIT_LOCATION,
                prompt="Введи локацию. Чтобы очистить поле, отправь `-`.",
                action_name="candidate_edit_location_start",
                parse_mode="Markdown",
            )

        if action == "candidate_menu_edit_about_me":
            return await self._handle_candidate_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_CANDIDATE_EDIT_ABOUT_ME,
                prompt="Введи текст «About me». Чтобы очистить поле, отправь `-`.",
                action_name="candidate_edit_about_me_start",
                parse_mode="Markdown",
            )

        if action == "candidate_menu_edit_work_modes":
            return await self._handle_candidate_edit_work_modes_choice_start(
                callback=callback,
                actor=actor,
            )

        if action == "candidate_menu_edit_english_level":
            return await self._handle_candidate_edit_english_choice_start(
                callback=callback,
                actor=actor,
            )

        if action == "candidate_menu_edit_status":
            return await self._handle_candidate_edit_status_choice_start(
                callback=callback,
                actor=actor,
            )

        if action == "candidate_menu_edit_salary":
            return await self._handle_candidate_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_CANDIDATE_EDIT_SALARY,
                prompt=(
                    "Введи зарплату в формате `min max currency`.\n"
                    "Пример: `250000 350000 RUB`.\n"
                    "Чтобы очистить зарплату, отправь `-`."
                ),
                action_name="candidate_edit_salary_start",
                parse_mode="Markdown",
            )

        if action == "candidate_menu_edit_skills":
            return await self._handle_candidate_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_CANDIDATE_EDIT_SKILLS,
                prompt=(
                    "Введи навыки, по одному на строку:\n"
                    "`skill; kind; level`\n"
                    "Разделитель: `;` (также поддерживается `|`).\n"
                    "kind: `hard`, `soft`, `tool`, `language`.\n"
                    "level: 1..5 (можно пусто).\n"
                    "Пример: `Python; hard; 5`\n"
                    "Чтобы очистить список, отправь `-`."
                ),
                action_name="candidate_edit_skills_start",
                parse_mode="Markdown",
            )

        if action == "candidate_menu_edit_education":
            return await self._handle_candidate_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_CANDIDATE_EDIT_EDUCATION,
                prompt=(
                    "Введи образование, по одному на строку:\n"
                    "`level; institution; year`\n"
                    "Разделитель: `;` (также поддерживается `|`).\n"
                    "Пример: `Bachelor; NSU; 2022`\n"
                    "Чтобы очистить список, отправь `-`."
                ),
                action_name="candidate_edit_education_start",
                parse_mode="Markdown",
            )

        if action == "candidate_menu_edit_experiences":
            return await self._handle_candidate_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_CANDIDATE_EDIT_EXPERIENCES,
                prompt=(
                    "Введи опыт, по одному на строку:\n"
                    "`company; position; start_date; end_date; responsibilities`\n"
                    "Разделитель: `;` (также поддерживается `|`).\n"
                    "Дата: `YYYY-MM-DD`, `end_date` можно пустым.\n"
                    "Пример: `Acme; Backend Developer; 2023-01-01; "
                    "2024-02-01; FastAPI и PostgreSQL`\n"
                    "Чтобы очистить список, отправь `-`."
                ),
                action_name="candidate_edit_experiences_start",
                parse_mode="Markdown",
            )

        if action == "candidate_menu_edit_projects":
            return await self._handle_candidate_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_CANDIDATE_EDIT_PROJECTS,
                prompt=(
                    "Введи проекты, по одному на строку:\n"
                    "`title; description; link1,link2`\n"
                    "Разделитель между полями: `;` (также поддерживается `|`).\n"
                    "Ссылки опциональны, только http/https.\n"
                    "Пример: `ATS Bot; Telegram recruiting bot; https://github.com/org/repo`\n"
                    "Чтобы очистить список, отправь `-`."
                ),
                action_name="candidate_edit_projects_start",
                parse_mode="Markdown",
            )

        if action == "candidate_menu_edit_contacts_visibility":
            return await self._handle_candidate_edit_contacts_visibility_choice_start(
                callback=callback,
                actor=actor,
            )

        if action == "candidate_menu_edit_contact_telegram":
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Telegram-контакт синхронизируется автоматически",
                show_alert=False,
            )
            return {"status": "processed", "action": "candidate_edit_contact_telegram_disabled"}

        if action == "candidate_menu_edit_contact_email":
            return await self._handle_candidate_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_CANDIDATE_EDIT_CONTACT_EMAIL,
                prompt=self._build_profile_contact_prompt(
                    contact_label="email",
                    example="name@example.com",
                ),
                action_name="candidate_edit_contact_email_start",
                parse_mode="Markdown",
            )

        if action == "candidate_menu_edit_contact_phone":
            return await self._handle_candidate_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_CANDIDATE_EDIT_CONTACT_PHONE,
                prompt=self._build_profile_contact_prompt(
                    contact_label="телефон",
                    example="+7 999 123-45-67",
                ),
                action_name="candidate_edit_contact_phone_start",
                parse_mode="Markdown",
            )

        if action == "candidate_menu_upload_avatar":
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_FILE_AWAIT_AVATAR,
                payload=None,
            )
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Загрузка аватара",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text="Отправь фото или изображение документом.",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_avatar_upload_started"}

        if action == "candidate_menu_upload_resume":
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_CANDIDATE,
                state_key=STATE_CANDIDATE_FILE_AWAIT_RESUME,
                payload=None,
            )
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Загрузка резюме",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text="Отправь резюме документом в формате PDF, DOC или DOCX.",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "candidate_resume_upload_started"}

        if action == "candidate_menu_download_avatar":
            return await self._handle_candidate_download_file(
                callback=callback,
                actor=actor,
                target_kind="avatar",
            )

        if action == "candidate_menu_download_resume":
            return await self._handle_candidate_download_file(
                callback=callback,
                actor=actor,
                target_kind="resume",
            )

        if action == "candidate_menu_delete_avatar":
            return await self._handle_candidate_delete_file(
                callback=callback,
                actor=actor,
                target_kind="avatar",
            )

        if action == "candidate_menu_delete_resume":
            return await self._handle_candidate_delete_file(
                callback=callback,
                actor=actor,
                target_kind="resume",
            )

        if action == "candidate_menu_contact_requests":
            return await self._handle_candidate_contact_requests_list(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "candidate_contact_request_refresh":
            return await self._handle_candidate_contact_requests_list(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "candidate_contact_request_open":
            return await self._handle_candidate_contact_request_open(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "candidate_contact_request_decision":
            return await self._handle_candidate_contact_request_decision(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "candidate_registration_continue":
            return await self._handle_candidate_registration_continue(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_registration_continue":
            return await self._handle_employer_registration_continue(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_menu_create_search":
            return await self._handle_employer_start_search_wizard(
                callback=callback,
                actor=actor,
            )

        if action == "employer_menu_edit_company":
            return await self._handle_employer_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_EMPLOYER_EDIT_COMPANY,
                prompt=self._build_profile_name_prompt(
                    field_label="название компании",
                    example="Acme Labs",
                ),
                action_name="employer_edit_company_start",
                parse_mode="Markdown",
            )

        if action == "employer_menu_edit_contact_telegram":
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Telegram-контакт синхронизируется автоматически",
                show_alert=False,
            )
            return {"status": "processed", "action": "employer_edit_contact_telegram_disabled"}

        if action == "employer_menu_edit_contact_email":
            return await self._handle_employer_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_EMPLOYER_EDIT_CONTACT_EMAIL,
                prompt=self._build_profile_contact_prompt(
                    contact_label="email",
                    example="hr@company.com",
                ),
                action_name="employer_edit_contact_email_start",
                parse_mode="Markdown",
            )

        if action == "employer_menu_edit_contact_phone":
            return await self._handle_employer_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_EMPLOYER_EDIT_CONTACT_PHONE,
                prompt=self._build_profile_contact_prompt(
                    contact_label="телефон",
                    example="+7 999 123-45-67",
                ),
                action_name="employer_edit_contact_phone_start",
                parse_mode="Markdown",
            )

        if action == "employer_menu_edit_contact_website":
            return await self._handle_employer_edit_start(
                callback=callback,
                actor=actor,
                state_key=STATE_EMPLOYER_EDIT_CONTACT_WEBSITE,
                prompt=self._build_profile_website_prompt(),
                action_name="employer_edit_contact_website_start",
                parse_mode="Markdown",
            )

        if action == "employer_menu_list_searches":
            return await self._handle_employer_list_searches(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_menu_favorites":
            return await self._handle_employer_favorites(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_menu_unlocked_contacts":
            return await self._handle_employer_unlocked_contacts(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_open_collection_candidate":
            return await self._handle_employer_open_collection_candidate(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_menu_upload_avatar":
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_FILE_AWAIT_AVATAR,
                payload=None,
            )
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Загрузка аватара",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text="Отправь фото или изображение документом для аватара компании.",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "employer_avatar_upload_started"}

        if action == "employer_menu_upload_document":
            await self._conversation_state_service.set_state(
                telegram_user_id=actor.id,
                role_context=ROLE_EMPLOYER,
                state_key=STATE_EMPLOYER_FILE_AWAIT_DOCUMENT,
                payload=None,
            )
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Загрузка документа",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text="Отправь документ компании в формате PDF, DOC или DOCX.",
                reply_markup=await self._build_stateful_cancel_markup(actor.id),
            )
            return {"status": "processed", "action": "employer_document_upload_started"}

        if action == "employer_menu_download_avatar":
            return await self._handle_employer_download_file(
                callback=callback,
                actor=actor,
                target_kind="avatar",
            )

        if action == "employer_menu_download_document":
            return await self._handle_employer_download_file(
                callback=callback,
                actor=actor,
                target_kind="document",
            )

        if action == "employer_menu_delete_avatar":
            return await self._handle_employer_delete_file(
                callback=callback,
                actor=actor,
                target_kind="avatar",
            )

        if action == "employer_menu_delete_document":
            return await self._handle_employer_delete_file(
                callback=callback,
                actor=actor,
                target_kind="document",
            )

        if action == "employer_menu_profile":
            return await self._handle_employer_profile(callback=callback, actor=actor)

        if action == "employer_menu_stats":
            return await self._handle_employer_stats(callback=callback, actor=actor)

        if action == "employer_menu_help":
            return await self._handle_employer_help(callback=callback, actor=actor)

        if action == "employer_menu_dashboard":
            return await self._handle_employer_dashboard(callback=callback, actor=actor)

        if action == "employer_menu_open_edit_section":
            return await self._handle_employer_open_edit_section(
                callback=callback,
                actor=actor,
            )

        if action == "employer_edit_cancel":
            return await self._handle_employer_edit_cancel(callback=callback, actor=actor)

        if action == "employer_menu_open_files_section":
            return await self._handle_employer_open_files_section(
                callback=callback,
                actor=actor,
            )

        if action == "employer_menu_open_search_section":
            return await self._handle_employer_open_search_section(
                callback=callback,
                actor=actor,
            )

        if action == "employer_menu_continue_active_search":
            return await self._handle_employer_continue_active_search(
                callback=callback, actor=actor
            )

        if action == "employer_menu_switch_role":
            return await self._handle_switch_role_from_menu(callback=callback, actor=actor)

        if action == "employer_search_create_confirm":
            return await self._handle_employer_search_create_confirm(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_search_confirm_back":
            return await self._handle_employer_search_confirm_back(
                callback=callback,
                actor=actor,
            )

        if action == "employer_search_confirm_edit_step":
            return await self._handle_employer_search_confirm_edit_step(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_search_wizard_skip":
            return await self._handle_employer_search_wizard_control(
                callback=callback,
                actor=actor,
                context=context,
                control="skip",
            )

        if action == "employer_search_wizard_cancel":
            return await self._handle_employer_search_wizard_control(
                callback=callback,
                actor=actor,
                context=context,
                control="cancel",
            )

        if action == "employer_search_wizard_back":
            return await self._handle_employer_search_wizard_control(
                callback=callback,
                actor=actor,
                context=context,
                control="back",
            )

        if action == "candidate_choice_work_mode_toggle":
            return await self._handle_candidate_choice_work_mode_toggle(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "candidate_choice_work_modes_done":
            return await self._handle_candidate_choice_work_modes_done(
                callback=callback,
                actor=actor,
            )

        if action == "candidate_choice_work_modes_clear":
            return await self._handle_candidate_choice_work_modes_clear(
                callback=callback,
                actor=actor,
            )

        if action == "candidate_choice_contacts_visibility":
            return await self._handle_candidate_choice_contacts_visibility(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "candidate_choice_english_level":
            return await self._handle_candidate_choice_english_level(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "candidate_choice_status":
            return await self._handle_candidate_choice_status(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_search_choice_work_mode_toggle":
            return await self._handle_employer_search_choice_work_mode_toggle(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_search_choice_work_modes_done":
            return await self._handle_employer_search_choice_work_modes_done(
                callback=callback,
                actor=actor,
            )

        if action == "employer_search_choice_english":
            return await self._handle_employer_search_choice_english(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_open_search":
            return await self._handle_employer_open_search(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_search_decision":
            return await self._handle_employer_search_decision(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_search_resume_download":
            return await self._handle_employer_search_resume_download(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_search_pause":
            return await self._handle_employer_search_control(
                callback=callback,
                actor=actor,
                context=context,
                operation="pause",
            )

        if action == "employer_search_resume":
            return await self._handle_employer_search_control(
                callback=callback,
                actor=actor,
                context=context,
                operation="resume",
            )

        if action == "employer_search_close":
            return await self._handle_employer_search_control(
                callback=callback,
                actor=actor,
                context=context,
                operation="close",
            )

        if action == "employer_request_contact_access":
            return await self._handle_employer_request_contact_access(
                callback=callback,
                actor=actor,
                context=context,
            )

        if action == "employer_next_candidate":
            return await self._handle_employer_next_candidate(
                callback=callback,
                actor=actor,
                context=context,
            )

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Неизвестное действие",
            show_alert=True,
        )
        mark_callback_failed("unknown_action")
        return {"status": "ignored", "reason": "unknown_callback_action"}
