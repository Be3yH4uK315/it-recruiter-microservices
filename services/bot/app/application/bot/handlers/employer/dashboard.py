from __future__ import annotations

from app.application.bot.constants import (
    ROLE_EMPLOYER,
    STATE_EMPLOYER_SEARCH_TITLE,
    WIZARD_SCREEN_MESSAGE_ID_KEY,
)
from app.application.common.gateway_errors import EmployerGatewayError
from app.application.observability.logging import get_logger
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser

logger = get_logger(__name__)


class EmployerDashboardHandlersMixin:
    async def _handle_employer_dashboard(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
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
        except EmployerGatewayError as exc:
            logger.warning(
                "employer dashboard load failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_menu_dashboard",
                retry_payload={},
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        if employer is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Профиль работодателя не найден",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_not_found"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Меню работодателя",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_employer_dashboard_message(
                first_name=actor.first_name,
                employer=employer,
                statistics=None,
                created_now=False,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": "employer_dashboard"}

    async def _handle_employer_start_search_wizard(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        payload: dict[str, object] = {}
        if callback.message is not None:
            payload[WIZARD_SCREEN_MESSAGE_ID_KEY] = callback.message.message_id
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Создание поиска",
            show_alert=False,
        )
        await self._set_state_and_render_wizard_step(
            telegram_user_id=actor.id,
            role_context=ROLE_EMPLOYER,
            state_key=STATE_EMPLOYER_SEARCH_TITLE,
            payload=payload,
            chat_id=self._resolve_chat_id(callback, actor),
            text=self._build_screen_message(
                section_path="Кабинет работодателя · Поиск · Новый поиск",
                title="Мастер поиска",
                body_lines=[
                    "*Введи название поиска*",
                    "",
                    "Например:",
                    "`Python backend middle`",
                ],
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_search_wizard_controls_markup(
                telegram_user_id=actor.id,
                step="title",
                allow_skip=False,
                allow_back=False,
            ),
        )
        return {"status": "processed", "action": "employer_search_create_started"}

    async def _handle_employer_open_edit_section(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Редактирование профиля",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_screen_message(
                section_path="Кабинет работодателя · Редактирование профиля",
                title="Редактирование кабинета работодателя",
                body_lines=["Выбери раздел, который хочешь обновить."],
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_edit_section_markup(telegram_user_id=actor.id),
        )
        return {"status": "processed", "action": "employer_menu_open_edit_section"}

    async def _handle_employer_edit_cancel(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Редактирование отменено",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_screen_message(
                section_path="Кабинет работодателя · Редактирование профиля",
                title="Редактирование кабинета работодателя",
                body_lines=["Выбери раздел, который хочешь обновить."],
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_edit_section_markup(
                telegram_user_id=actor.id
            ),
        )
        return {"status": "processed", "action": "employer_edit_cancel"}

    async def _handle_employer_open_files_section(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
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
        except EmployerGatewayError as exc:
            logger.warning(
                "employer files section load failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_menu_open_files_section",
                retry_payload={},
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        if employer is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Профиль работодателя не найден",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_not_found"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Раздел файлов",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_screen_message(
                section_path="Кабинет работодателя · Файлы компании",
                title="Файлы компании",
                body_lines=[
                    "Здесь можно загрузить, скачать или удалить аватар и документ компании."
                ],
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_files_section_markup(
                telegram_user_id=actor.id,
                has_avatar=bool(employer.avatar_file_id or employer.avatar_download_url),
                has_document=bool(employer.document_file_id or employer.document_download_url),
            ),
        )
        return {"status": "processed", "action": "employer_menu_open_files_section"}

    async def _handle_employer_open_search_section(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
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
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Профиль работодателя не найден",
                    show_alert=True,
                )
                return {"status": "processed", "action": "employer_not_found"}

            searches = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.list_searches(
                    access_token=token,
                    employer_id=employer.id,
                    limit=20,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer search section load failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_menu_open_search_section",
                retry_payload={},
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        has_active_search = any(self._is_search_active(item.status) for item in searches)
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Раздел поиска",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_screen_message(
                section_path="Кабинет работодателя · Поиск",
                title="Поиск кандидатов",
                body_lines=[
                    "Выбери действие: активная сессия, список поисков, избранные или открытые контакты."
                ],
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_search_section_markup(
                telegram_user_id=actor.id,
                has_active_search=has_active_search,
            ),
        )
        return {"status": "processed", "action": "employer_menu_open_search_section"}

    async def _handle_employer_continue_active_search(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
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
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Профиль работодателя не найден",
                    show_alert=True,
                )
                return {"status": "processed", "action": "employer_not_found"}

            searches = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.list_searches(
                    access_token=token,
                    employer_id=employer.id,
                    limit=20,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer continue active search failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_menu_continue_active_search",
                retry_payload={},
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        active_search = next(
            (item for item in searches if self._is_search_active(item.status)),
            None,
        )
        if active_search is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Активный поиск не найден",
                show_alert=False,
            )
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=self._build_screen_message(
                    section_path="Кабинет работодателя · Поиск · Активная сессия",
                    title="Активная сессия",
                    body_lines=[
                        "ℹ️ Активный поиск не найден.",
                        "",
                        "Создай новый поиск или открой список всех поисков.",
                    ],
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_employer_search_section_markup(
                    telegram_user_id=actor.id,
                    has_active_search=False,
                ),
            )
            return {"status": "processed", "action": "employer_continue_active_search_empty"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Нашел активный поиск",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_screen_message(
                section_path="Кабинет работодателя · Поиск · Активная сессия",
                title="Активная сессия",
                body_lines=[
                    f"🔎 *Название:* {active_search.title}",
                    f"💼 *Роль:* {active_search.role or '—'}",
                    f"📊 *Статус:* {self._humanize_search_status(active_search.status)}",
                ],
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_open_search_markup(
                telegram_user_id=actor.id,
                session_id=active_search.id,
                search_status=active_search.status,
            ),
        )
        return {"status": "processed", "action": "employer_continue_active_search"}

    async def _handle_employer_profile(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
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
        except EmployerGatewayError as exc:
            logger.warning(
                "employer profile load failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_menu_profile",
                retry_payload={},
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        if employer is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Профиль работодателя не найден",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_not_found"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Мой профиль",
            show_alert=False,
        )
        await self._render_callback_screen_with_optional_photo(
            callback=callback,
            actor=actor,
            text=self._build_employer_profile_message(
                employer=employer,
            ),
            photo_url=employer.avatar_download_url,
            fallback_photo_caption="🏢 Аватар профиля работодателя",
            parse_mode="Markdown",
            reply_markup=await self._build_employer_profile_view_markup(
                telegram_user_id=actor.id,
                employer=employer,
            ),
        )
        return {"status": "processed", "action": "employer_profile"}

    async def _handle_employer_help(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Помощь",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_employer_help_message(),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_back_to_dashboard_markup(
                telegram_user_id=actor.id
            ),
        )
        return {"status": "processed", "action": "employer_help"}

    async def _handle_employer_stats(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
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
        except EmployerGatewayError as exc:
            logger.warning(
                "employer stats profile load failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="employer",
                retry_action="employer_menu_stats",
                retry_payload={},
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        if employer is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Профиль работодателя не найден",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_not_found"}

        stats = await self._safe_get_employer_statistics(
            access_token=access_token,
            employer_id=employer.id,
        )

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Статистика работодателя",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_employer_stats_message(employer, stats),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_back_to_dashboard_markup(
                telegram_user_id=actor.id
            ),
        )
        return {"status": "processed", "action": "employer_stats"}
