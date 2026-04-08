from __future__ import annotations

from app.application.bot.constants import (
    CONTACT_VISIBILITY_HIDDEN,
    CONTACT_VISIBILITY_ON_REQUEST,
    CONTACT_VISIBILITY_PUBLIC,
)
from app.application.common.contracts import CandidateProfileSummary


class CandidateKeyboardsMixin:
    async def _build_candidate_dashboard_markup(self, telegram_user_id: int) -> dict:
        profile_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_profile",
            payload={},
        )
        edit_section_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_open_edit_section",
            payload={},
        )
        files_section_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_open_files_section",
            payload={},
        )
        contacts_section_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_open_contacts_section",
            payload={},
        )
        stats_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_stats",
            payload={},
        )
        contact_requests_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_contact_requests",
            payload={"page": 1},
        )
        help_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_help",
            payload={},
        )
        switch_role_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_switch_role",
            payload={},
        )

        return {
            "inline_keyboard": [
                [
                    {"text": "👤 Мой профиль", "callback_data": profile_token},
                    {"text": "✏️ Редактировать профиль", "callback_data": edit_section_token},
                ],
                [
                    {"text": "📁 Файлы", "callback_data": files_section_token},
                    {"text": "🔐 Контакты", "callback_data": contacts_section_token},
                ],
                [
                    {"text": "📊 Статистика", "callback_data": stats_token},
                    {"text": "📨 Запросы контактов", "callback_data": contact_requests_token},
                ],
                [{"text": "🆘 Помощь", "callback_data": help_token}],
                [{"text": "🔄 Сменить роль", "callback_data": switch_role_token}],
            ]
        }

    async def _build_candidate_files_section_markup(
        self,
        *,
        telegram_user_id: int,
        has_avatar: bool,
        has_resume: bool,
    ) -> dict:
        back_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_dashboard",
            payload={},
        )
        rows: list[list[dict[str, str]]] = []
        buttons: list[dict[str, str]] = []

        if has_avatar:
            download_avatar_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_menu_download_avatar",
                payload={},
            )
            delete_avatar_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_menu_delete_avatar",
                payload={},
            )
            buttons.append({"text": "⬇️ Скачать аватар", "callback_data": download_avatar_token})
            buttons.append({"text": "🗑 Удалить аватар", "callback_data": delete_avatar_token})
        else:
            upload_avatar_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_menu_upload_avatar",
                payload={},
            )
            buttons.append({"text": "🖼 Загрузить аватар", "callback_data": upload_avatar_token})

        if has_resume:
            download_resume_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_menu_download_resume",
                payload={},
            )
            delete_resume_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_menu_delete_resume",
                payload={},
            )
            buttons.append({"text": "⬇️ Скачать резюме", "callback_data": download_resume_token})
            buttons.append({"text": "🗑 Удалить резюме", "callback_data": delete_resume_token})
        else:
            upload_resume_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_menu_upload_resume",
                payload={},
            )
            buttons.append({"text": "📄 Загрузить резюме", "callback_data": upload_resume_token})

        for index in range(0, len(buttons), 2):
            rows.append(buttons[index : index + 2])

        rows.append([{"text": "⬅️ В меню", "callback_data": back_token}])
        return {"inline_keyboard": rows}

    async def _build_candidate_contacts_section_markup(
        self,
        *,
        telegram_user_id: int,
    ) -> dict:
        edit_contacts_visibility_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_contacts_visibility",
            payload={},
        )
        edit_status_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_status",
            payload={},
        )
        edit_contact_email_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_contact_email",
            payload={},
        )
        edit_contact_phone_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_contact_phone",
            payload={},
        )
        back_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_dashboard",
            payload={},
        )
        return {
            "inline_keyboard": [
                [
                    {"text": "👁 Видимость", "callback_data": edit_contacts_visibility_token},
                    {"text": "📊 Статус", "callback_data": edit_status_token},
                ],
                [
                    {"text": "📧 Email", "callback_data": edit_contact_email_token},
                    {"text": "📱 Телефон", "callback_data": edit_contact_phone_token},
                ],
                [{"text": "⬅️ В меню", "callback_data": back_token}],
            ]
        }

    async def _build_candidate_back_to_dashboard_markup(
        self,
        *,
        telegram_user_id: int,
    ) -> dict:
        back_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_dashboard",
            payload={},
        )
        return {
            "inline_keyboard": [
                [{"text": "⬅️ В меню", "callback_data": back_token}],
            ]
        }

    async def _build_candidate_edit_prompt_markup(
        self,
        *,
        telegram_user_id: int,
    ) -> dict:
        cancel_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_edit_cancel",
            payload={},
        )
        return {
            "inline_keyboard": [
                [{"text": "🛑 Отменить", "callback_data": cancel_token}],
            ]
        }

    async def _build_candidate_contact_requests_list_markup(
        self,
        *,
        telegram_user_id: int,
        requests: list,
        page: int = 1,
        total_pages: int = 1,
    ) -> dict:
        rows: list[list[dict[str, str]]] = []
        paged_requests, current_page, resolved_total_pages = self._paginate_items(
            requests,
            page=page,
        )
        if total_pages > resolved_total_pages:
            resolved_total_pages = total_pages
        for item in paged_requests:
            request_id_raw = getattr(item, "id", None)
            if request_id_raw is None:
                continue
            open_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_contact_request_open",
                payload={"request_id": str(request_id_raw)},
            )
            company = str(getattr(item, "employer_company", "") or "Компания")
            rows.append(
                [
                    {
                        "text": f"📨 Запрос: {company[:34]}",
                        "callback_data": open_token,
                    }
                ]
            )

        refresh_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_contact_request_refresh",
            payload={"page": current_page},
        )
        back_to_menu_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_dashboard",
            payload={},
        )
        if resolved_total_pages > 1:
            nav_row: list[dict[str, str]] = []
            if current_page > 1:
                prev_token = await self._create_callback_context(
                    telegram_user_id=telegram_user_id,
                    action_type="candidate_contact_request_refresh",
                    payload={"page": current_page - 1},
                )
                nav_row.append({"text": "⬅️", "callback_data": prev_token})
            page_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_contact_request_refresh",
                payload={"page": current_page},
            )
            nav_row.append(
                {
                    "text": f"Стр. {current_page}/{resolved_total_pages}",
                    "callback_data": page_token,
                }
            )
            if current_page < resolved_total_pages:
                next_token = await self._create_callback_context(
                    telegram_user_id=telegram_user_id,
                    action_type="candidate_contact_request_refresh",
                    payload={"page": current_page + 1},
                )
                nav_row.append({"text": "➡️", "callback_data": next_token})
            rows.append(nav_row)
        rows.append([{"text": "🔄 Обновить", "callback_data": refresh_token}])
        rows.append([{"text": "⬅️ В меню", "callback_data": back_to_menu_token}])
        return {"inline_keyboard": rows}

    async def _build_candidate_profile_view_markup(
        self,
        *,
        telegram_user_id: int,
        candidate: CandidateProfileSummary,
    ) -> dict:
        edit_menu_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_profile_edit_menu",
            payload={},
        )
        back_to_menu_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_dashboard",
            payload={},
        )

        first_row: list[dict[str, str]] = [
            {"text": "✏️ Редактировать профиль", "callback_data": edit_menu_token}
        ]
        if candidate.resume_download_url:
            download_resume_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_menu_download_resume",
                payload={},
            )
            first_row.append({"text": "⬇️ Скачать резюме", "callback_data": download_resume_token})

        rows: list[list[dict[str, str]]] = [first_row]
        rows.append([{"text": "⬅️ В меню", "callback_data": back_to_menu_token}])
        return {"inline_keyboard": rows}

    async def _build_candidate_profile_edit_menu_markup(
        self,
        *,
        telegram_user_id: int,
    ) -> dict:
        edit_display_name_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_display_name",
            payload={},
        )
        edit_headline_role_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_headline_role",
            payload={},
        )
        edit_location_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_location",
            payload={},
        )
        edit_about_me_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_about_me",
            payload={},
        )
        edit_work_modes_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_work_modes",
            payload={},
        )
        edit_english_level_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_english_level",
            payload={},
        )
        edit_salary_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_salary",
            payload={},
        )
        edit_skills_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_skills",
            payload={},
        )
        edit_education_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_education",
            payload={},
        )
        edit_experiences_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_experiences",
            payload={},
        )
        edit_projects_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_edit_projects",
            payload={},
        )
        back_to_profile_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_profile",
            payload={},
        )
        back_to_dashboard_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_menu_dashboard",
            payload={},
        )
        return {
            "inline_keyboard": [
                [
                    {"text": "👤 Имя", "callback_data": edit_display_name_token},
                    {"text": "💼 Роль", "callback_data": edit_headline_role_token},
                ],
                [
                    {"text": "📍 Локация", "callback_data": edit_location_token},
                    {"text": "💰 Зарплата", "callback_data": edit_salary_token},
                ],
                [
                    {"text": "💻 Формат работы", "callback_data": edit_work_modes_token},
                    {"text": "🇬🇧 Английский", "callback_data": edit_english_level_token},
                ],
                [
                    {"text": "🎓 Образование", "callback_data": edit_education_token},
                    {"text": "📜 Опыт работы", "callback_data": edit_experiences_token},
                ],
                [
                    {"text": "🛠 Навыки", "callback_data": edit_skills_token},
                    {"text": "🚀 Проекты", "callback_data": edit_projects_token},
                ],
                [{"text": "📝 О себе", "callback_data": edit_about_me_token}],
                [
                    {"text": "⬅️ К профилю", "callback_data": back_to_profile_token},
                    {"text": "⬅️ В меню", "callback_data": back_to_dashboard_token},
                ],
            ]
        }

    async def _build_candidate_work_modes_selector_markup(
        self,
        *,
        telegram_user_id: int,
        selected_modes: list[str] | None,
        allow_clear: bool,
    ) -> dict:
        selected = {
            str(item).strip().lower() for item in (selected_modes or []) if str(item).strip()
        }
        rows: list[list[dict[str, str]]] = []
        for mode, label in [
            ("remote", "🏠 Удаленно"),
            ("onsite", "🏢 Офис"),
            ("hybrid", "📌 Гибрид"),
        ]:
            toggle_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_choice_work_mode_toggle",
                payload={"mode": mode},
            )
            prefix = "✅ " if mode in selected else ""
            rows.append([{"text": f"{prefix}{label}", "callback_data": toggle_token}])
        done_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_choice_work_modes_done",
            payload={},
        )
        rows.append([{"text": "💾 Сохранить выбор", "callback_data": done_token}])
        if allow_clear:
            clear_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_choice_work_modes_clear",
                payload={},
            )
            rows.append([{"text": "🧹 Очистить выбор", "callback_data": clear_token}])
        return {"inline_keyboard": rows}

    async def _build_candidate_contacts_visibility_selector_markup(
        self,
        *,
        telegram_user_id: int,
        selected_visibility: str | None,
    ) -> dict:
        selected = str(selected_visibility or "").strip().lower()
        rows: list[list[dict[str, str]]] = []
        for value, label in [
            (CONTACT_VISIBILITY_PUBLIC, "🌍 Видны всем"),
            (CONTACT_VISIBILITY_ON_REQUEST, "🔒 По запросу"),
            (CONTACT_VISIBILITY_HIDDEN, "🚫 Скрыты"),
        ]:
            token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_choice_contacts_visibility",
                payload={"value": value},
            )
            prefix = "✅ " if value == selected else ""
            rows.append([{"text": f"{prefix}{label}", "callback_data": token}])
        return {"inline_keyboard": rows}

    async def _build_candidate_english_level_selector_markup(
        self,
        *,
        telegram_user_id: int,
        selected_level: str | None,
        allow_clear: bool,
    ) -> dict:
        selected = str(selected_level or "").strip().upper()
        levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        rows: list[list[dict[str, str]]] = []
        for left, right in [(levels[0], levels[1]), (levels[2], levels[3]), (levels[4], levels[5])]:
            left_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_choice_english_level",
                payload={"value": left},
            )
            right_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_choice_english_level",
                payload={"value": right},
            )
            left_prefix = "✅ " if selected == left else ""
            right_prefix = "✅ " if selected == right else ""
            rows.append(
                [
                    {"text": f"{left_prefix}{left}", "callback_data": left_token},
                    {"text": f"{right_prefix}{right}", "callback_data": right_token},
                ]
            )
        if allow_clear:
            clear_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="candidate_choice_english_level",
                payload={"value": ""},
            )
            rows.append([{"text": "🧹 Очистить / Пропустить", "callback_data": clear_token}])
        return {"inline_keyboard": rows}

    async def _build_candidate_status_selector_markup(
        self,
        *,
        telegram_user_id: int,
        selected_status: str | None,
    ) -> dict:
        selected = str(selected_status or "").strip().lower()
        active_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_choice_status",
            payload={"value": "active"},
        )
        hidden_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="candidate_choice_status",
            payload={"value": "hidden"},
        )
        return {
            "inline_keyboard": [
                [
                    {
                        "text": f"{'✅ ' if selected == 'active' else ''}Активен",
                        "callback_data": active_token,
                    }
                ],
                [
                    {
                        "text": f"{'✅ ' if selected == 'hidden' else ''}Скрыт",
                        "callback_data": hidden_token,
                    }
                ],
            ]
        }
