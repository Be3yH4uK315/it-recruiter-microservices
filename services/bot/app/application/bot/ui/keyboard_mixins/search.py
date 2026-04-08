from __future__ import annotations

from uuid import UUID

from app.application.bot.constants import DECISION_DISLIKE, DECISION_LIKE, DECISION_SKIP
from app.application.common.contracts import CandidateProfileSummary


class SearchKeyboardsMixin:
    async def _build_employer_search_create_confirm_markup(
        self,
        telegram_user_id: int,
    ) -> dict:
        edit_title_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_confirm_edit_step",
            payload={"step": "title"},
        )
        edit_role_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_confirm_edit_step",
            payload={"step": "role"},
        )
        edit_must_skills_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_confirm_edit_step",
            payload={"step": "must_skills"},
        )
        edit_nice_skills_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_confirm_edit_step",
            payload={"step": "nice_skills"},
        )
        edit_experience_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_confirm_edit_step",
            payload={"step": "experience"},
        )
        edit_location_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_confirm_edit_step",
            payload={"step": "location"},
        )
        edit_work_modes_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_confirm_edit_step",
            payload={"step": "work_modes"},
        )
        edit_salary_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_confirm_edit_step",
            payload={"step": "salary"},
        )
        edit_english_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_confirm_edit_step",
            payload={"step": "english"},
        )
        edit_about_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_confirm_edit_step",
            payload={"step": "about"},
        )
        back_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_confirm_back",
            payload={},
        )
        confirm_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_create_confirm",
            payload={"confirm": True},
        )
        cancel_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_create_confirm",
            payload={"confirm": False},
        )
        return {
            "inline_keyboard": [
                [
                    {"text": "✏️ Название", "callback_data": edit_title_token},
                    {"text": "✏️ Роль", "callback_data": edit_role_token},
                ],
                [
                    {"text": "🧠 Обязательные", "callback_data": edit_must_skills_token},
                    {"text": "🛠 Желательные", "callback_data": edit_nice_skills_token},
                ],
                [
                    {"text": "📈 Опыт", "callback_data": edit_experience_token},
                    {"text": "📍 Локация", "callback_data": edit_location_token},
                ],
                [
                    {"text": "💻 Формат", "callback_data": edit_work_modes_token},
                    {"text": "💰 Зарплата", "callback_data": edit_salary_token},
                ],
                [
                    {"text": "🇬🇧 Английский", "callback_data": edit_english_token},
                    {"text": "📝 Описание", "callback_data": edit_about_token},
                ],
                [{"text": "⬅️ Назад к шагам", "callback_data": back_token}],
                [{"text": "✅ Создать поиск", "callback_data": confirm_token}],
                [{"text": "🛑 Отменить", "callback_data": cancel_token}],
            ]
        }

    async def _build_employer_search_wizard_controls_markup(
        self,
        *,
        telegram_user_id: int,
        step: str,
        allow_skip: bool,
        allow_back: bool = True,
    ) -> dict:
        rows: list[list[dict[str, str]]] = []
        nav_row: list[dict[str, str]] = []
        if allow_skip:
            skip_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_search_wizard_skip",
                payload={"step": step},
            )
            nav_row.append({"text": "⏭ Пропустить", "callback_data": skip_token})

        if allow_back:
            back_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_search_wizard_back",
                payload={"step": step},
            )
            nav_row.insert(0, {"text": "⬅️ Назад", "callback_data": back_token})

        if nav_row:
            rows.append(nav_row)

        cancel_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_wizard_cancel",
            payload={"step": step},
        )
        rows.append([{"text": "🛑 Отменить создание", "callback_data": cancel_token}])
        return {"inline_keyboard": rows}

    async def _build_employer_search_work_modes_selector_markup(
        self,
        *,
        telegram_user_id: int,
        selected_modes: list[str] | None,
        allow_skip: bool,
        allow_back: bool = True,
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
                action_type="employer_search_choice_work_mode_toggle",
                payload={"mode": mode},
            )
            prefix = "✅ " if mode in selected else ""
            rows.append([{"text": f"{prefix}{label}", "callback_data": toggle_token}])

        done_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_choice_work_modes_done",
            payload={},
        )
        rows.append([{"text": "💾 Сохранить выбор", "callback_data": done_token}])

        controls = await self._build_employer_search_wizard_controls_markup(
            telegram_user_id=telegram_user_id,
            step="work_modes",
            allow_skip=allow_skip,
            allow_back=allow_back,
        )
        rows.extend(controls.get("inline_keyboard", []))
        return {"inline_keyboard": rows}

    async def _build_employer_search_english_selector_markup(
        self,
        *,
        telegram_user_id: int,
        selected_level: str | None,
        allow_skip: bool,
        allow_back: bool = True,
    ) -> dict:
        selected = str(selected_level or "").strip().upper()
        rows: list[list[dict[str, str]]] = []
        for left, right in [("A1", "A2"), ("B1", "B2"), ("C1", "C2")]:
            left_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_search_choice_english",
                payload={"value": left},
            )
            right_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_search_choice_english",
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

        clear_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_choice_english",
            payload={"value": ""},
        )
        rows.append([{"text": "🧹 Очистить", "callback_data": clear_token}])

        if allow_skip:
            skip_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_search_wizard_skip",
                payload={"step": "english"},
            )
            rows.append([{"text": "⏭ Пропустить", "callback_data": skip_token}])

        controls = await self._build_employer_search_wizard_controls_markup(
            telegram_user_id=telegram_user_id,
            step="english",
            allow_skip=False,
            allow_back=allow_back,
        )
        rows.extend(controls.get("inline_keyboard", []))
        return {"inline_keyboard": rows}

    async def _build_open_search_markup(
        self,
        telegram_user_id: int,
        session_id: UUID,
        search_status: str | None = None,
    ) -> dict:
        token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_open_search",
            payload={"session_id": str(session_id), "search_status": search_status},
        )
        control_rows = await self._build_search_control_rows(
            telegram_user_id=telegram_user_id,
            session_id=session_id,
            search_status=search_status,
        )
        keyboard: list[list[dict[str, str]]] = []
        if not self._is_search_closed(search_status):
            keyboard.append([{"text": "▶️ Открыть поиск", "callback_data": token}])
        keyboard.extend(control_rows)
        return {"inline_keyboard": keyboard}

    async def _build_next_candidate_only_markup(
        self,
        *,
        telegram_user_id: int,
        session_id: UUID,
        search_status: str | None = None,
    ) -> dict:
        keyboard: list[list[dict[str, str]]] = []
        if self._is_search_active(search_status):
            next_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_next_candidate",
                payload={"session_id": str(session_id), "search_status": search_status},
            )
            keyboard.append([{"text": "➡️ Следующий кандидат", "callback_data": next_token}])

        keyboard.extend(
            await self._build_search_control_rows(
                telegram_user_id=telegram_user_id,
                session_id=session_id,
                search_status=search_status,
            )
        )
        list_searches_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_list_searches",
            payload={"page": 1},
        )
        keyboard.append([{"text": "🗂 К списку поисков", "callback_data": list_searches_token}])
        return {"inline_keyboard": keyboard}

    async def _build_no_candidate_markup(
        self,
        *,
        telegram_user_id: int,
        session_id: UUID,
        search_status: str | None = None,
        is_degraded: bool = False,
    ) -> dict:
        keyboard: list[list[dict[str, str]]] = []
        if self._is_search_active(search_status):
            next_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_next_candidate",
                payload={"session_id": str(session_id), "search_status": search_status},
            )
            button_text = "🔁 Повторить" if is_degraded else "➡️ Следующий кандидат"
            keyboard.append([{"text": button_text, "callback_data": next_token}])

        keyboard.extend(
            await self._build_search_control_rows(
                telegram_user_id=telegram_user_id,
                session_id=session_id,
                search_status=search_status,
            )
        )
        list_searches_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_list_searches",
            payload={"page": 1},
        )
        keyboard.append([{"text": "🗂 К списку поисков", "callback_data": list_searches_token}])
        return {"inline_keyboard": keyboard}

    async def _build_after_like_markup(
        self,
        *,
        telegram_user_id: int,
        session_id: UUID,
        candidate_id: UUID,
        search_status: str | None = None,
    ) -> dict:
        request_contacts_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_request_contact_access",
            payload={
                "session_id": str(session_id),
                "candidate_id": str(candidate_id),
                "search_status": search_status,
                "liked": True,
            },
        )
        next_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_next_candidate",
            payload={"session_id": str(session_id), "search_status": search_status},
        )

        keyboard: list[list[dict[str, str]]] = [
            [{"text": "🔓 Запросить контакты", "callback_data": request_contacts_token}],
        ]
        if self._is_search_active(search_status):
            keyboard.append([{"text": "➡️ Следующий кандидат", "callback_data": next_token}])

        keyboard.extend(
            await self._build_search_control_rows(
                telegram_user_id=telegram_user_id,
                session_id=session_id,
                search_status=search_status,
            )
        )
        list_searches_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_list_searches",
            payload={"page": 1},
        )
        keyboard.append([{"text": "🗂 К списку поисков", "callback_data": list_searches_token}])
        return {"inline_keyboard": keyboard}

    async def _build_candidate_decision_markup(
        self,
        *,
        telegram_user_id: int,
        session_id: UUID,
        candidate: CandidateProfileSummary | None,
        search_status: str | None = None,
    ) -> dict:
        if candidate is None:
            return {"inline_keyboard": []}

        if not self._is_search_active(search_status):
            return await self._build_next_candidate_only_markup(
                telegram_user_id=telegram_user_id,
                session_id=session_id,
                search_status=search_status,
            )

        like_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_decision",
            payload={
                "session_id": str(session_id),
                "candidate_id": str(candidate.id),
                "decision": DECISION_LIKE,
                "search_status": search_status,
                "can_view_contacts": candidate.can_view_contacts,
            },
        )
        dislike_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_decision",
            payload={
                "session_id": str(session_id),
                "candidate_id": str(candidate.id),
                "decision": DECISION_DISLIKE,
                "search_status": search_status,
                "can_view_contacts": candidate.can_view_contacts,
            },
        )
        skip_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_search_decision",
            payload={
                "session_id": str(session_id),
                "candidate_id": str(candidate.id),
                "decision": DECISION_SKIP,
                "search_status": search_status,
                "can_view_contacts": candidate.can_view_contacts,
            },
        )

        keyboard: list[list[dict[str, str]]] = [
            [
                {"text": "👍 Подходит", "callback_data": like_token},
                {"text": "👎 Не подходит", "callback_data": dislike_token},
                {"text": "⏭ Пропустить", "callback_data": skip_token},
            ]
        ]
        if candidate.resume_download_url:
            resume_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_search_resume_download",
                payload={
                    "session_id": str(session_id),
                    "candidate_id": str(candidate.id),
                    "search_status": search_status,
                    "resume_download_url": candidate.resume_download_url,
                },
            )
            keyboard.append([{"text": "📄 Открыть резюме", "callback_data": resume_token}])

        keyboard.extend(
            await self._build_search_control_rows(
                telegram_user_id=telegram_user_id,
                session_id=session_id,
                search_status=search_status,
            )
        )
        list_searches_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_list_searches",
            payload={"page": 1},
        )
        keyboard.append([{"text": "🗂 К списку поисков", "callback_data": list_searches_token}])
        return {"inline_keyboard": keyboard}

    async def _build_search_control_rows(
        self,
        *,
        telegram_user_id: int,
        session_id: UUID,
        search_status: str | None = None,
    ) -> list[list[dict[str, str]]]:
        normalized_status = self._normalize_search_status(search_status)
        control_rows: list[list[dict[str, str]]] = []

        if not self._is_search_closed(normalized_status):
            close_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_search_close",
                payload={
                    "session_id": str(session_id),
                    "search_status": normalized_status,
                },
            )
            if self._is_search_paused(normalized_status):
                resume_token = await self._create_callback_context(
                    telegram_user_id=telegram_user_id,
                    action_type="employer_search_resume",
                    payload={
                        "session_id": str(session_id),
                        "search_status": normalized_status,
                    },
                )
                control_rows.append(
                    [{"text": "▶️ Возобновить поиск", "callback_data": resume_token}]
                )
                control_rows.append([{"text": "⛔ Закрыть поиск", "callback_data": close_token}])
                return control_rows

            pause_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_search_pause",
                payload={
                    "session_id": str(session_id),
                    "search_status": normalized_status,
                },
            )
            control_rows.append([{"text": "⏸ Поставить на паузу", "callback_data": pause_token}])
            control_rows.append([{"text": "⛔ Закрыть поиск", "callback_data": close_token}])

        return control_rows
