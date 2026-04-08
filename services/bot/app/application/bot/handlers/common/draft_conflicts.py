from __future__ import annotations

from app.application.bot.constants import (
    DRAFT_CONFLICT_NAV_ACTIONS,
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
    STATE_EMPLOYER_SEARCH_CONFIRM,
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
from app.application.state.services.conversation_state_service import ConversationStateView
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser


class DraftConflictHandlersMixin:
    @staticmethod
    def _should_prompt_draft_conflict(
        *,
        state: ConversationStateView | None,
        action: str,
    ) -> bool:
        if state is None or not state.state_key:
            return False
        if action not in DRAFT_CONFLICT_NAV_ACTIONS:
            return False
        return True

    async def _handle_draft_conflict_prompt(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        state: ConversationStateView,
        target_action: str,
        target_payload: dict | None,
    ) -> dict:
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Есть незавершённое действие",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_status_screen(
                section_path="Черновик",
                title="Есть незавершённое действие",
                status_line="ℹ️ У тебя есть незавершённый шаг.",
                details=[
                    f"Текущее действие: {self._build_draft_conflict_state_label(state.state_key)}",
                    "Выбери, что сделать:",
                ],
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_draft_conflict_markup(
                telegram_user_id=actor.id,
                target_action=target_action,
                target_payload=target_payload,
            ),
        )
        return {"status": "processed", "action": "draft_conflict_prompt"}

    async def _build_draft_conflict_markup(
        self,
        *,
        telegram_user_id: int,
        target_action: str,
        target_payload: dict | None,
    ) -> dict:
        payload: dict[str, object] = {
            "target_action": target_action,
            "target_payload": target_payload if isinstance(target_payload, dict) else {},
        }
        continue_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="draft_conflict_continue",
            payload=payload,
        )
        reset_and_go_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="draft_conflict_reset_and_go",
            payload=payload,
        )
        return {
            "inline_keyboard": [
                [{"text": "↩️ Продолжить действие", "callback_data": continue_token}],
                [{"text": "🧹 Сбросить черновик и перейти", "callback_data": reset_and_go_token}],
            ]
        }

    async def _build_start_resume_draft_markup(
        self,
        *,
        telegram_user_id: int,
    ) -> dict:
        continue_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="start_resume_continue",
            payload={},
        )
        reset_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="start_resume_reset",
            payload={},
        )
        return {
            "inline_keyboard": [
                [{"text": "↩️ Да, продолжить", "callback_data": continue_token}],
                [{"text": "🧹 Сбросить и выбрать роль", "callback_data": reset_token}],
            ]
        }

    async def _handle_start_resume_continue(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Продолжаем",
            show_alert=False,
        )
        if state is None or not state.state_key:
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=self._build_status_screen(
                    section_path="Черновик",
                    title="Черновик не найден",
                    status_line="ℹ️ Активного черновика нет.",
                    details=["Выбери роль для продолжения."],
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_role_selection_markup(telegram_user_id=actor.id),
            )
            return {"status": "processed", "action": "start_resume_continue_no_state"}

        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_draft_continue_message(state),
        )
        return {"status": "processed", "action": "start_resume_continue"}

    async def _handle_start_resume_reset(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Черновик сброшен",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_role_selection_message(actor=actor),
            parse_mode="Markdown",
            reply_markup=await self._build_role_selection_markup(telegram_user_id=actor.id),
        )
        return {"status": "processed", "action": "start_resume_reset"}

    async def _handle_draft_conflict_continue(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        state = await self._conversation_state_service.get_state(telegram_user_id=actor.id)
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Продолжаем текущий шаг",
            show_alert=False,
        )
        if state is None or not state.state_key:
            target_action = str(context.payload.get("target_action", "")).strip()
            raw_target_payload = context.payload.get("target_payload")
            target_payload = raw_target_payload if isinstance(raw_target_payload, dict) else {}
            executed = await self._execute_post_conflict_navigation_action(
                callback=callback,
                actor=actor,
                target_action=target_action,
                target_payload=target_payload,
            )
            if executed is not None:
                return executed
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=self._build_status_screen(
                    section_path="Черновик",
                    title="Черновик уже завершён",
                    status_line="ℹ️ Черновик уже завершён или сброшен.",
                    details=["Можешь открыть нужный раздел снова через меню."],
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "draft_conflict_continue_no_state"}

        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_draft_continue_message(state),
        )
        return {"status": "processed", "action": "draft_conflict_continue"}

    async def _handle_draft_conflict_reset_and_go(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        target_action = str(context.payload.get("target_action", "")).strip()
        raw_target_payload = context.payload.get("target_payload")
        target_payload = raw_target_payload if isinstance(raw_target_payload, dict) else {}

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Черновик сброшен",
            show_alert=False,
        )

        executed = await self._execute_post_conflict_navigation_action(
            callback=callback,
            actor=actor,
            target_action=target_action,
            target_payload=target_payload,
        )
        if executed is not None:
            return executed

        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_status_screen(
                section_path="Черновик",
                title="Черновик сброшен",
                status_line="⚠️ Перейти в выбранный раздел не удалось.",
                details=["Нажми `/start` и открой нужный пункт меню."],
            ),
            parse_mode="Markdown",
        )
        return {"status": "processed", "action": "draft_conflict_reset_unknown_action"}

    async def _execute_post_conflict_navigation_action(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        target_action: str,
        target_payload: dict,
    ) -> dict | None:
        context = ResolvedCallbackContext(
            action_type=target_action,
            payload=target_payload,
        )
        if target_action == "select_role":
            return await self._handle_select_role_callback(
                callback=callback,
                actor=actor,
                context=context,
            )
        if target_action == "candidate_menu_dashboard":
            return await self._handle_candidate_dashboard(callback=callback, actor=actor)
        if target_action == "candidate_menu_profile":
            return await self._handle_candidate_profile(callback=callback, actor=actor)
        if target_action in {
            "candidate_menu_profile_edit_menu",
            "candidate_menu_open_edit_section",
        }:
            return await self._handle_candidate_profile_edit_menu(callback=callback, actor=actor)
        if target_action == "candidate_menu_open_files_section":
            return await self._handle_candidate_open_files_section(callback=callback, actor=actor)
        if target_action == "candidate_menu_open_contacts_section":
            return await self._handle_candidate_open_contacts_section(
                callback=callback, actor=actor
            )
        if target_action == "candidate_menu_stats":
            return await self._handle_candidate_stats(callback=callback, actor=actor)
        if target_action == "candidate_menu_contact_requests":
            return await self._handle_candidate_contact_requests_list(
                callback=callback,
                actor=actor,
                context=context,
            )
        if target_action == "candidate_menu_help":
            return await self._handle_candidate_help(callback=callback, actor=actor)
        if target_action == "candidate_menu_switch_role":
            return await self._handle_switch_role_from_menu(callback=callback, actor=actor)

        if target_action == "employer_menu_dashboard":
            return await self._handle_employer_dashboard(callback=callback, actor=actor)
        if target_action == "employer_menu_profile":
            return await self._handle_employer_profile(callback=callback, actor=actor)
        if target_action == "employer_menu_open_edit_section":
            return await self._handle_employer_open_edit_section(callback=callback, actor=actor)
        if target_action == "employer_menu_open_files_section":
            return await self._handle_employer_open_files_section(callback=callback, actor=actor)
        if target_action == "employer_menu_open_search_section":
            return await self._handle_employer_open_search_section(callback=callback, actor=actor)
        if target_action == "employer_menu_create_search":
            return await self._handle_employer_start_search_wizard(callback=callback, actor=actor)
        if target_action == "employer_menu_continue_active_search":
            return await self._handle_employer_continue_active_search(
                callback=callback, actor=actor
            )
        if target_action == "employer_menu_list_searches":
            return await self._handle_employer_list_searches(
                callback=callback,
                actor=actor,
                context=context,
            )
        if target_action == "employer_menu_favorites":
            return await self._handle_employer_favorites(
                callback=callback,
                actor=actor,
                context=context,
            )
        if target_action == "employer_menu_unlocked_contacts":
            return await self._handle_employer_unlocked_contacts(
                callback=callback,
                actor=actor,
                context=context,
            )
        if target_action == "employer_menu_stats":
            return await self._handle_employer_stats(callback=callback, actor=actor)
        if target_action == "employer_menu_help":
            return await self._handle_employer_help(callback=callback, actor=actor)
        if target_action == "employer_menu_switch_role":
            return await self._handle_switch_role_from_menu(callback=callback, actor=actor)

        return None

    @staticmethod
    def _build_draft_conflict_state_label(state_key: str) -> str:
        mapping = {
            STATE_CANDIDATE_REG_DISPLAY_NAME: "Регистрация кандидата: имя",
            STATE_CANDIDATE_REG_HEADLINE_ROLE: "Регистрация кандидата: роль",
            STATE_CANDIDATE_REG_WORK_MODES: "Регистрация кандидата: формат работы",
            STATE_CANDIDATE_REG_CONTACTS_VISIBILITY: "Регистрация кандидата: видимость контактов",
            STATE_CANDIDATE_REG_ENGLISH_LEVEL: "Регистрация кандидата: английский",
            STATE_CANDIDATE_REG_SALARY: "Регистрация кандидата: зарплата",
            STATE_CANDIDATE_REG_LOCATION: "Регистрация кандидата: локация",
            STATE_CANDIDATE_REG_ABOUT_ME: "Регистрация кандидата: о себе",
            STATE_CANDIDATE_REG_CONTACT_EMAIL: "Регистрация кандидата: контакт email",
            STATE_CANDIDATE_REG_CONTACT_PHONE: "Регистрация кандидата: контакт phone",
            STATE_CANDIDATE_REG_SKILLS: "Регистрация кандидата: навыки",
            STATE_CANDIDATE_REG_EDUCATION: "Регистрация кандидата: образование",
            STATE_CANDIDATE_REG_EXPERIENCES: "Регистрация кандидата: опыт",
            STATE_CANDIDATE_REG_PROJECTS: "Регистрация кандидата: проекты",
            STATE_CANDIDATE_EDIT_DISPLAY_NAME: "Редактирование кандидата: имя",
            STATE_CANDIDATE_EDIT_HEADLINE_ROLE: "Редактирование кандидата: роль",
            STATE_CANDIDATE_EDIT_LOCATION: "Редактирование кандидата: локация",
            STATE_CANDIDATE_EDIT_ABOUT_ME: "Редактирование кандидата: о себе",
            STATE_CANDIDATE_EDIT_WORK_MODES: "Редактирование кандидата: формат работы",
            STATE_CANDIDATE_EDIT_ENGLISH_LEVEL: "Редактирование кандидата: английский",
            STATE_CANDIDATE_EDIT_STATUS: "Редактирование кандидата: статус",
            STATE_CANDIDATE_EDIT_SALARY: "Редактирование кандидата: зарплата",
            STATE_CANDIDATE_EDIT_SKILLS: "Редактирование кандидата: навыки",
            STATE_CANDIDATE_EDIT_EDUCATION: "Редактирование кандидата: образование",
            STATE_CANDIDATE_EDIT_EXPERIENCES: "Редактирование кандидата: опыт",
            STATE_CANDIDATE_EDIT_PROJECTS: "Редактирование кандидата: проекты",
            STATE_CANDIDATE_EDIT_CONTACTS_VISIBILITY: (
                "Редактирование кандидата: видимость контактов"
            ),
            STATE_CANDIDATE_EDIT_CONTACT_TELEGRAM: "Редактирование кандидата: контакт telegram",
            STATE_CANDIDATE_EDIT_CONTACT_EMAIL: "Редактирование кандидата: контакт email",
            STATE_CANDIDATE_EDIT_CONTACT_PHONE: "Редактирование кандидата: контакт phone",
            STATE_EMPLOYER_REG_COMPANY: "Регистрация работодателя: компания",
            STATE_EMPLOYER_REG_CONTACT_TELEGRAM: "Регистрация работодателя: telegram",
            STATE_EMPLOYER_REG_CONTACT_EMAIL: "Регистрация работодателя: email",
            STATE_EMPLOYER_REG_CONTACT_PHONE: "Регистрация работодателя: phone",
            STATE_EMPLOYER_REG_CONTACT_WEBSITE: "Регистрация работодателя: website",
            STATE_EMPLOYER_EDIT_COMPANY: "Редактирование работодателя: компания",
            STATE_EMPLOYER_EDIT_CONTACT_TELEGRAM: "Редактирование работодателя: контакт telegram",
            STATE_EMPLOYER_EDIT_CONTACT_EMAIL: "Редактирование работодателя: контакт email",
            STATE_EMPLOYER_EDIT_CONTACT_PHONE: "Редактирование работодателя: контакт phone",
            STATE_EMPLOYER_EDIT_CONTACT_WEBSITE: "Редактирование работодателя: контакт website",
            STATE_EMPLOYER_SEARCH_TITLE: "Новый поиск: название",
            STATE_EMPLOYER_SEARCH_ROLE: "Новый поиск: роль",
            STATE_EMPLOYER_SEARCH_MUST_SKILLS: "Новый поиск: обязательные навыки",
            STATE_EMPLOYER_SEARCH_NICE_SKILLS: "Новый поиск: желательные навыки",
            STATE_EMPLOYER_SEARCH_EXPERIENCE: "Новый поиск: опыт",
            STATE_EMPLOYER_SEARCH_LOCATION: "Новый поиск: локация",
            STATE_EMPLOYER_SEARCH_WORK_MODES: "Новый поиск: формат работы",
            STATE_EMPLOYER_SEARCH_SALARY: "Новый поиск: зарплата",
            STATE_EMPLOYER_SEARCH_ENGLISH: "Новый поиск: английский",
            STATE_EMPLOYER_SEARCH_ABOUT: "Новый поиск: описание",
            STATE_EMPLOYER_SEARCH_CONFIRM: "Новый поиск: подтверждение",
            STATE_CANDIDATE_FILE_AWAIT_AVATAR: "Загрузка файла: аватар кандидата",
            STATE_CANDIDATE_FILE_AWAIT_RESUME: "Загрузка файла: резюме кандидата",
            STATE_EMPLOYER_FILE_AWAIT_AVATAR: "Загрузка файла: аватар компании",
            STATE_EMPLOYER_FILE_AWAIT_DOCUMENT: "Загрузка файла: документ компании",
        }
        return mapping.get(state_key, state_key)

    def _build_draft_continue_message(self, state: ConversationStateView) -> str:
        lines = [
            "Продолжаем текущее действие.",
            "",
            f"Текущий шаг: {self._build_draft_conflict_state_label(state.state_key)}",
        ]
        if state.state_key in {
            STATE_EMPLOYER_SEARCH_TITLE,
            STATE_EMPLOYER_SEARCH_ROLE,
            STATE_EMPLOYER_SEARCH_MUST_SKILLS,
            STATE_EMPLOYER_SEARCH_NICE_SKILLS,
            STATE_EMPLOYER_SEARCH_EXPERIENCE,
            STATE_EMPLOYER_SEARCH_LOCATION,
            STATE_EMPLOYER_SEARCH_WORK_MODES,
            STATE_EMPLOYER_SEARCH_SALARY,
            STATE_EMPLOYER_SEARCH_ENGLISH,
            STATE_EMPLOYER_SEARCH_ABOUT,
            STATE_EMPLOYER_SEARCH_CONFIRM,
        } and isinstance(state.payload, dict):
            step_by_state = {
                STATE_EMPLOYER_SEARCH_TITLE: "title",
                STATE_EMPLOYER_SEARCH_ROLE: "role",
                STATE_EMPLOYER_SEARCH_MUST_SKILLS: "must_skills",
                STATE_EMPLOYER_SEARCH_NICE_SKILLS: "nice_skills",
                STATE_EMPLOYER_SEARCH_EXPERIENCE: "experience",
                STATE_EMPLOYER_SEARCH_LOCATION: "location",
                STATE_EMPLOYER_SEARCH_WORK_MODES: "work_modes",
                STATE_EMPLOYER_SEARCH_SALARY: "salary",
                STATE_EMPLOYER_SEARCH_ENGLISH: "english",
                STATE_EMPLOYER_SEARCH_ABOUT: "about",
            }
            step = step_by_state.get(state.state_key)
            if step is not None:
                lines.extend(
                    [
                        "",
                        "Текущий выбор:",
                        self._build_employer_search_step_current_value(state.payload, step),
                    ]
                )
            elif state.state_key == STATE_EMPLOYER_SEARCH_CONFIRM:
                lines.extend(
                    [
                        "",
                        self._build_employer_search_filters_summary(state.payload),
                    ]
                )

        if state.state_key in {
            STATE_CANDIDATE_FILE_AWAIT_AVATAR,
            STATE_CANDIDATE_FILE_AWAIT_RESUME,
            STATE_EMPLOYER_FILE_AWAIT_AVATAR,
            STATE_EMPLOYER_FILE_AWAIT_DOCUMENT,
        }:
            lines.extend(
                [
                    "",
                    (
                        "Отправь файл в чат, чтобы завершить этот шаг, "
                        "или используй /cancel для выхода в меню."
                    ),
                ]
            )
            return "\n".join(lines)

        lines.extend(
            [
                "",
                (
                    "Отправь сообщение, чтобы продолжить этот шаг, "
                    "или используй /cancel для выхода в меню."
                ),
            ]
        )
        return "\n".join(lines)
