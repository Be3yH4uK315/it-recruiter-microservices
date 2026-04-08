from __future__ import annotations

from app.application.common.gateway_errors import CandidateGatewayError
from app.application.observability.logging import get_logger
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser

logger = get_logger(__name__)


class CandidateDashboardHandlersMixin:
    async def _handle_candidate_profile(
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
                "candidate profile load failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="candidate",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="candidate",
                retry_action="candidate_menu_profile",
                retry_payload={},
            )
            return {"status": "processed", "action": "candidate_gateway_error"}

        if candidate is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Профиль кандидата не найден",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_not_found"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Мой профиль",
            show_alert=False,
        )
        await self._render_callback_screen_with_optional_photo(
            callback=callback,
            actor=actor,
            text=self._build_candidate_profile_message(
                candidate=candidate,
            ),
            photo_url=candidate.avatar_download_url,
            fallback_photo_caption="👤 Аватар профиля кандидата",
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_profile_view_markup(
                telegram_user_id=actor.id,
                candidate=candidate,
            ),
        )
        return {"status": "processed", "action": "candidate_profile"}

    async def _handle_candidate_dashboard(
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
                "candidate dashboard load failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="candidate",
            )
            return {"status": "processed", "action": "candidate_gateway_error"}

        if candidate is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Профиль кандидата не найден",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_not_found"}

        stats = await self._safe_get_candidate_statistics(
            access_token=access_token,
            candidate_id=candidate.id,
        )

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Меню кандидата",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_candidate_dashboard_message(
                first_name=actor.first_name,
                candidate=candidate,
                statistics=stats,
                created_now=False,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": "candidate_dashboard"}

    async def _handle_candidate_profile_edit_menu(
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
                section_path="Кабинет кандидата · Профиль · Редактирование",
                title="Редактирование профиля кандидата",
                body_lines=["Выбери блок, который хочешь обновить."],
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_profile_edit_menu_markup(
                telegram_user_id=actor.id
            ),
        )
        return {"status": "processed", "action": "candidate_profile_edit_menu"}

    async def _handle_candidate_edit_cancel(
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
                section_path="Кабинет кандидата · Профиль · Редактирование",
                title="Редактирование профиля кандидата",
                body_lines=["Выбери блок, который хочешь обновить."],
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_profile_edit_menu_markup(
                telegram_user_id=actor.id
            ),
        )
        return {"status": "processed", "action": "candidate_edit_cancel"}

    async def _handle_candidate_open_files_section(
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
                "candidate files section load failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="candidate",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="candidate",
                retry_action="candidate_menu_open_files_section",
                retry_payload={},
            )
            return {"status": "processed", "action": "candidate_gateway_error"}

        if candidate is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Профиль кандидата не найден",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_not_found"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Раздел файлов",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_screen_message(
                section_path="Кабинет кандидата · Файлы",
                title="Файлы кандидата",
                body_lines=["Здесь можно загрузить, скачать и удалить аватар или резюме."],
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_files_section_markup(
                telegram_user_id=actor.id,
                has_avatar=bool(candidate.avatar_file_id or candidate.avatar_download_url),
                has_resume=bool(candidate.resume_file_id or candidate.resume_download_url),
            ),
        )
        return {"status": "processed", "action": "candidate_menu_open_files_section"}

    async def _handle_candidate_open_contacts_section(
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
                "candidate contacts section load failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="candidate",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="candidate",
                retry_action="candidate_menu_open_contacts_section",
                retry_payload={},
            )
            return {"status": "processed", "action": "candidate_gateway_error"}

        if candidate is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Профиль кандидата не найден",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_not_found"}

        contacts_block = "\n".join(
            self._build_candidate_contacts_block_lines(
                contacts=candidate.contacts,
                contacts_visibility=candidate.contacts_visibility,
                can_view_contacts=True,
                contacts_title="📞 *Ваши контакты:*",
            )
        )

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Раздел контактов",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_screen_message(
                section_path="Кабинет кандидата · Контакты и видимость",
                title="Контакты и приватность",
                body_lines=[
                    f"📊 *Статус профиля:* {self._humanize_candidate_status(candidate.status)}",
                    "",
                    contacts_block,
                ],
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_contacts_section_markup(
                telegram_user_id=actor.id
            ),
        )
        return {"status": "processed", "action": "candidate_menu_open_contacts_section"}

    async def _handle_candidate_help(
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
            text=self._build_candidate_help_message(),
            reply_markup=await self._build_candidate_back_to_dashboard_markup(
                telegram_user_id=actor.id
            ),
        )
        return {"status": "processed", "action": "candidate_help"}

    async def _handle_candidate_stats(
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
                "candidate stats profile load failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="candidate",
            )
            await self._send_retry_action_if_temporarily_unavailable(
                chat_id=self._resolve_chat_id(callback, actor),
                telegram_user_id=actor.id,
                exc=exc,
                gateway_type="candidate",
                retry_action="candidate_menu_stats",
                retry_payload={},
            )
            return {"status": "processed", "action": "candidate_gateway_error"}

        if candidate is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Профиль кандидата не найден",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_not_found"}

        stats = await self._safe_get_candidate_statistics(
            access_token=access_token,
            candidate_id=candidate.id,
        )

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Статистика кандидата",
            show_alert=False,
        )
        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_candidate_stats_message(candidate, stats),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_back_to_dashboard_markup(
                telegram_user_id=actor.id
            ),
        )
        return {"status": "processed", "action": "candidate_stats"}
