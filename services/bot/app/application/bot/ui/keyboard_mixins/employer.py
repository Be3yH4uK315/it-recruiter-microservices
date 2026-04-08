from __future__ import annotations

from app.application.common.contracts import (
    CandidateProfileSummary,
    EmployerProfileSummary,
    SearchSessionSummary,
)


class EmployerKeyboardsMixin:
    async def _build_employer_dashboard_markup(self, telegram_user_id: int) -> dict:
        profile = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_profile",
            payload={},
        )
        edit_section = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_open_edit_section",
            payload={},
        )
        search_section = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_open_search_section",
            payload={},
        )
        create_search = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_create_search",
            payload={},
        )
        list_searches = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_list_searches",
            payload={"page": 1},
        )
        favorites = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_favorites",
            payload={"page": 1},
        )
        unlocked = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_unlocked_contacts",
            payload={"page": 1},
        )
        files_section = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_open_files_section",
            payload={},
        )
        stats = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_stats",
            payload={},
        )
        help = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_help",
            payload={},
        )
        switch_role = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_switch_role",
            payload={},
        )
        return {
            "inline_keyboard": [
                [
                    {"text": "🏢 Мой профиль", "callback_data": profile},
                    {"text": "✏️ Редактировать профиль", "callback_data": edit_section},
                ],
                [
                    {"text": "🔎 Поиск", "callback_data": search_section},
                    {"text": "📁 Файлы", "callback_data": files_section},
                ],
                [
                    {"text": "🆕 Новый поиск", "callback_data": create_search},
                    {"text": "🗂 Все поиски", "callback_data": list_searches},
                ],
                [
                    {"text": "⭐ Избранные контакты", "callback_data": favorites},
                    {"text": "🔓 Открытые контакты", "callback_data": unlocked},
                ],
                [
                    {"text": "📊 Статистика", "callback_data": stats},
                    {"text": "🆘 Помощь", "callback_data": help},
                ],
                [{"text": "🔄 Сменить роль", "callback_data": switch_role}],
            ]
        }

    async def _build_employer_edit_section_markup(
        self,
        *,
        telegram_user_id: int,
    ) -> dict:
        edit_company = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_edit_company",
            payload={},
        )
        edit_contact_email = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_edit_contact_email",
            payload={},
        )
        edit_contact_phone = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_edit_contact_phone",
            payload={},
        )
        edit_contact_website = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_edit_contact_website",
            payload={},
        )
        back_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_dashboard",
            payload={},
        )
        return {
            "inline_keyboard": [
                [{"text": "🏢 Компания", "callback_data": edit_company}],
                [
                    {"text": "📧 Email", "callback_data": edit_contact_email},
                    {"text": "📱 Телефон", "callback_data": edit_contact_phone},
                ],
                [{"text": "🌐 Website", "callback_data": edit_contact_website}],
                [{"text": "⬅️ В меню", "callback_data": back_token}],
            ]
        }

    async def _build_employer_edit_prompt_markup(
        self,
        *,
        telegram_user_id: int,
    ) -> dict:
        cancel_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_edit_cancel",
            payload={},
        )
        return {
            "inline_keyboard": [
                [{"text": "🛑 Отменить", "callback_data": cancel_token}],
            ]
        }

    async def _build_employer_files_section_markup(
        self,
        *,
        telegram_user_id: int,
        has_avatar: bool,
        has_document: bool,
    ) -> dict:
        back_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_dashboard",
            payload={},
        )
        rows: list[list[dict[str, str]]] = []
        buttons: list[dict[str, str]] = []

        if has_avatar:
            download_avatar = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_menu_download_avatar",
                payload={},
            )
            delete_avatar = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_menu_delete_avatar",
                payload={},
            )
            buttons.append({"text": "⬇️ Скачать аватар", "callback_data": download_avatar})
            buttons.append({"text": "🗑 Удалить аватар", "callback_data": delete_avatar})
        else:
            upload_avatar = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_menu_upload_avatar",
                payload={},
            )
            buttons.append({"text": "🖼 Загрузить аватар", "callback_data": upload_avatar})

        if has_document:
            download_document = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_menu_download_document",
                payload={},
            )
            delete_document = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_menu_delete_document",
                payload={},
            )
            buttons.append({"text": "⬇️ Скачать документ", "callback_data": download_document})
            buttons.append({"text": "🗑 Удалить документ", "callback_data": delete_document})
        else:
            upload_document = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_menu_upload_document",
                payload={},
            )
            buttons.append({"text": "📄 Загрузить документ", "callback_data": upload_document})

        for index in range(0, len(buttons), 2):
            rows.append(buttons[index : index + 2])

        rows.append([{"text": "⬅️ В меню", "callback_data": back_token}])
        return {"inline_keyboard": rows}

    async def _build_employer_back_to_dashboard_markup(
        self,
        *,
        telegram_user_id: int,
    ) -> dict:
        back_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_dashboard",
            payload={},
        )
        return {
            "inline_keyboard": [
                [{"text": "⬅️ В меню", "callback_data": back_token}],
            ]
        }

    async def _build_employer_profile_view_markup(
        self,
        *,
        telegram_user_id: int,
        employer: EmployerProfileSummary,
    ) -> dict:
        edit_profile_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_open_edit_section",
            payload={},
        )
        back_to_menu_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_dashboard",
            payload={},
        )

        first_row: list[dict[str, str]] = [
            {"text": "✏️ Редактировать профиль", "callback_data": edit_profile_token}
        ]
        if employer.document_download_url:
            download_document_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_menu_download_document",
                payload={},
            )
            first_row.append(
                {"text": "⬇️ Скачать документ", "callback_data": download_document_token}
            )

        rows: list[list[dict[str, str]]] = [first_row]
        rows.append([{"text": "⬅️ В меню", "callback_data": back_to_menu_token}])
        return {"inline_keyboard": rows}

    async def _build_employer_search_section_markup(
        self,
        *,
        telegram_user_id: int,
        has_active_search: bool = False,
    ) -> dict:
        create_search = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_create_search",
            payload={},
        )
        continue_active = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_continue_active_search",
            payload={},
        )
        list_searches = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_list_searches",
            payload={"page": 1},
        )
        favorites = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_favorites",
            payload={"page": 1},
        )
        unlocked = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_unlocked_contacts",
            payload={"page": 1},
        )
        back_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_dashboard",
            payload={},
        )
        first_row: list[dict[str, str]] = [
            {"text": "🆕 Новый поиск", "callback_data": create_search},
        ]
        if has_active_search:
            first_row.append({"text": "▶️ Продолжить активный", "callback_data": continue_active})
        return {
            "inline_keyboard": [
                first_row,
                [
                    {"text": "🗂 Все поиски", "callback_data": list_searches},
                    {"text": "⭐ Избранные контакты", "callback_data": favorites},
                ],
                [{"text": "🔓 Открытые контакты", "callback_data": unlocked}],
                [{"text": "⬅️ В меню", "callback_data": back_token}],
            ]
        }

    async def _build_employer_searches_empty_markup(
        self,
        *,
        telegram_user_id: int,
    ) -> dict:
        back_to_search_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_open_search_section",
            payload={},
        )
        back_to_menu_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_dashboard",
            payload={},
        )
        return {
            "inline_keyboard": [
                [{"text": "⬅️ К поиску", "callback_data": back_to_search_token}],
                [{"text": "⬅️ В меню", "callback_data": back_to_menu_token}],
            ]
        }

    async def _build_searches_list_markup(
        self,
        telegram_user_id: int,
        searches: list[SearchSessionSummary],
        *,
        page: int = 1,
        total_pages: int = 1,
    ) -> dict:
        rows: list[list[dict[str, str]]] = []
        paged_searches, current_page, resolved_total_pages = self._paginate_items(
            searches,
            page=page,
        )
        if total_pages > resolved_total_pages:
            resolved_total_pages = total_pages
        for item in paged_searches:
            if self._is_search_closed(item.status):
                continue
            token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_open_search",
                payload={"session_id": str(item.id), "search_status": item.status},
            )
            rows.append(
                [
                    {
                        "text": f"🔎 {item.title} · {self._humanize_search_status(item.status)}",
                        "callback_data": token,
                    }
                ]
            )
        if resolved_total_pages > 1:
            nav_row: list[dict[str, str]] = []
            if current_page > 1:
                prev_token = await self._create_callback_context(
                    telegram_user_id=telegram_user_id,
                    action_type="employer_menu_list_searches",
                    payload={"page": current_page - 1},
                )
                nav_row.append({"text": "⬅️", "callback_data": prev_token})
            page_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_menu_list_searches",
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
                    action_type="employer_menu_list_searches",
                    payload={"page": current_page + 1},
                )
                nav_row.append({"text": "➡️", "callback_data": next_token})
            rows.append(nav_row)
        back_to_search_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_open_search_section",
            payload={},
        )
        back_to_menu_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_dashboard",
            payload={},
        )
        rows.append(
            [
                {"text": "⬅️ К поиску", "callback_data": back_to_search_token},
                {"text": "⬅️ В меню", "callback_data": back_to_menu_token},
            ]
        )
        return {"inline_keyboard": rows}

    async def _build_candidate_collection_markup(
        self,
        *,
        telegram_user_id: int,
        items: list[CandidateProfileSummary],
        source: str,
        page: int = 1,
        total_pages: int = 1,
    ) -> dict | None:
        if source not in {"favorites", "unlocked"}:
            return None

        rows: list[list[dict[str, str]]] = []
        paged_items, current_page, resolved_total_pages = self._paginate_items(
            items,
            page=page,
        )
        if total_pages > resolved_total_pages:
            resolved_total_pages = total_pages
        for item in paged_items:
            if self._is_search_closed(getattr(item, "status", None)):
                continue
            token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type="employer_open_collection_candidate",
                payload={
                    "source": source,
                    "candidate_id": str(item.id),
                    "page": current_page,
                    "total_pages": resolved_total_pages,
                },
            )
            rows.append(
                [
                    {
                        "text": f"👤 {item.display_name}",
                        "callback_data": token,
                    }
                ]
            )

        if resolved_total_pages > 1:
            nav_action = (
                "employer_menu_favorites"
                if source == "favorites"
                else "employer_menu_unlocked_contacts"
            )
            nav_row: list[dict[str, str]] = []
            if current_page > 1:
                prev_token = await self._create_callback_context(
                    telegram_user_id=telegram_user_id,
                    action_type=nav_action,
                    payload={"page": current_page - 1},
                )
                nav_row.append({"text": "⬅️", "callback_data": prev_token})
            page_token = await self._create_callback_context(
                telegram_user_id=telegram_user_id,
                action_type=nav_action,
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
                    action_type=nav_action,
                    payload={"page": current_page + 1},
                )
                nav_row.append({"text": "➡️", "callback_data": next_token})
            rows.append(nav_row)

        back_to_search_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_open_search_section",
            payload={},
        )
        back_to_menu_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type="employer_menu_dashboard",
            payload={},
        )
        rows.append(
            [
                {"text": "⬅️ К поиску", "callback_data": back_to_search_token},
                {"text": "⬅️ В меню", "callback_data": back_to_menu_token},
            ]
        )
        return {"inline_keyboard": rows}

    async def _build_candidate_collection_profile_markup(
        self,
        *,
        telegram_user_id: int,
        source: str,
        page: int,
        total_pages: int,
    ) -> dict | None:
        if source not in {"favorites", "unlocked"}:
            return None

        list_action = (
            "employer_menu_favorites" if source == "favorites" else "employer_menu_unlocked_contacts"
        )
        back_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type=list_action,
            payload={"page": page},
        )
        return {"inline_keyboard": [[{"text": "⬅️ К списку", "callback_data": back_token}]]}
