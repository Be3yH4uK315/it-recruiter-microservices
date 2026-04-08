from __future__ import annotations

from app.application.bot.constants import ROLE_EMPLOYER, STATE_EMPLOYER_FILE_AWAIT_AVATAR
from app.application.common.gateway_errors import EmployerGatewayError
from app.application.common.telegram_api import TelegramApiError
from app.application.employer.services.file_flow_service import EmployerFileFlowError
from app.application.observability.logging import get_logger
from app.application.observability.metrics import mark_file_upload
from app.application.state.services.conversation_state_service import ConversationStateView
from app.schemas.telegram import TelegramCallbackQuery, TelegramMessage, TelegramUser

logger = get_logger(__name__)


class EmployerFileHandlersMixin:
    def _build_employer_file_status_message(
        self,
        *,
        title: str,
        status_line: str,
        details: list[str] | None = None,
    ) -> str:
        return self._build_status_screen(
            section_path="Кабинет работодателя · Файлы компании",
            title=title,
            status_line=status_line,
            details=details,
        )

    async def _handle_employer_file_upload_state(
        self,
        *,
        message: TelegramMessage,
        actor: TelegramUser,
        state: ConversationStateView,
        chat_id: int,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=self._build_employer_file_status_message(
                    title="Сессия истекла",
                    status_line="⚠️ Сессия устарела.",
                    details=["Нажми `/start`, чтобы выбрать роль заново."],
                ),
                parse_mode="Markdown",
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
        except EmployerGatewayError as exc:
            logger.warning(
                "employer file flow profile load failed",
                extra={"telegram_user_id": actor.id, "state_key": state.state_key},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_employer_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "employer_gateway_error"}

        if employer is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=self._build_employer_file_status_message(
                    title="Профиль не найден",
                    status_line="⚠️ Профиль работодателя не найден.",
                    details=["Нажми `/start`, чтобы начать заново."],
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "employer_not_found"}

        try:
            if state.state_key == STATE_EMPLOYER_FILE_AWAIT_AVATAR:
                await self._employer_file_flow_service.process_avatar_upload(
                    access_token=access_token,
                    telegram_user_id=actor.id,
                    employer_id=employer.id,
                    message=message,
                )
                success_text = "Аватар компании успешно обновлён."
                action_name = "employer_avatar_uploaded"
            else:
                await self._employer_file_flow_service.process_document_upload(
                    access_token=access_token,
                    telegram_user_id=actor.id,
                    employer_id=employer.id,
                    message=message,
                )
                success_text = "Документ компании успешно обновлён."
                action_name = "employer_document_uploaded"
        except EmployerFileFlowError as exc:
            kind = (
                "employer_avatar"
                if state.state_key == STATE_EMPLOYER_FILE_AWAIT_AVATAR
                else "employer_document"
            )
            mark_file_upload(ROLE_EMPLOYER, kind, "validation_failed")
            await self._telegram_client.send_message(chat_id=chat_id, text=str(exc))
            return {"status": "processed", "action": "employer_file_upload_validation_failed"}
        except EmployerGatewayError as exc:
            kind = (
                "employer_avatar"
                if state.state_key == STATE_EMPLOYER_FILE_AWAIT_AVATAR
                else "employer_document"
            )
            mark_file_upload(ROLE_EMPLOYER, kind, "gateway_failed")
            logger.warning(
                "employer file flow gateway failed",
                extra={"telegram_user_id": actor.id, "state_key": state.state_key},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_employer_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "employer_gateway_error"}
        except Exception as exc:
            kind = (
                "employer_avatar"
                if state.state_key == STATE_EMPLOYER_FILE_AWAIT_AVATAR
                else "employer_document"
            )
            mark_file_upload(ROLE_EMPLOYER, kind, "failed")
            logger.warning(
                "employer file flow failed",
                extra={"telegram_user_id": actor.id, "state_key": state.state_key},
                exc_info=exc,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=self._build_employer_file_status_message(
                    title="Файл не обработан",
                    status_line="⚠️ Не удалось обработать файл.",
                    details=["Попробуй отправить его ещё раз."],
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "employer_file_upload_failed"}
        mark_file_upload(
            ROLE_EMPLOYER,
            (
                "employer_avatar"
                if state.state_key == STATE_EMPLOYER_FILE_AWAIT_AVATAR
                else "employer_document"
            ),
            "linked",
        )

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)

        try:
            refreshed = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
        except EmployerGatewayError:
            refreshed = None

        if refreshed is None:
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=self._build_employer_file_status_message(
                    title="Файл обновлён",
                    status_line=f"✅ {success_text}",
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": action_name}

        stats = await self._safe_get_employer_statistics(
            access_token=access_token,
            employer_id=refreshed.id,
        )
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=f"✅ *{success_text}*\n\n"
            + self._build_employer_dashboard_message(
                first_name=actor.first_name,
                employer=refreshed,
                statistics=stats,
                created_now=False,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": action_name}

    async def _handle_employer_download_file(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        target_kind: str,
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
                "employer download file load failed",
                extra={"telegram_user_id": actor.id, "target_kind": target_kind},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        if employer is None:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Профиль работодателя не найден",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_not_found"}

        download_url = (
            employer.avatar_download_url
            if target_kind == "avatar"
            else employer.document_download_url
        )
        if not download_url:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Файл не загружен",
                show_alert=True,
            )
            return {"status": "processed", "action": "employer_download_file_missing"}

        chat_id = self._resolve_chat_id(callback, actor)
        try:
            if target_kind == "avatar":
                await self._telegram_client.send_photo(
                    chat_id=chat_id,
                    photo=download_url,
                    caption="Текущий аватар компании",
                )
                action_name = "employer_avatar_downloaded"
            else:
                await self._telegram_client.send_document(
                    chat_id=chat_id,
                    document=download_url,
                    caption="Текущий документ компании",
                )
                action_name = "employer_document_downloaded"
        except TelegramApiError:
            await self._telegram_client.send_attachment_message(
                chat_id=chat_id,
                text=f"Ссылка на файл:\n{download_url}",
            )
            action_name = (
                "employer_avatar_download_link_sent"
                if target_kind == "avatar"
                else "employer_document_download_link_sent"
            )

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Готово",
            show_alert=False,
        )
        return {"status": "processed", "action": action_name}

    async def _handle_employer_delete_file(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        target_kind: str,
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

            if target_kind == "avatar":
                idempotency_key = self._build_idempotency_key(
                    telegram_user_id=actor.id,
                    operation="employer.avatar.delete",
                    resource_id=employer.id,
                )
                await self._run_employer_gateway_call(
                    telegram_user_id=actor.id,
                    access_token=access_token,
                    operation=lambda token: self._employer_gateway.delete_avatar(
                        access_token=token,
                        employer_id=employer.id,
                        idempotency_key=idempotency_key,
                    ),
                )
                success_text = "Аватар компании удалён."
                action_name = "employer_avatar_deleted"
            else:
                idempotency_key = self._build_idempotency_key(
                    telegram_user_id=actor.id,
                    operation="employer.document.delete",
                    resource_id=employer.id,
                )
                await self._run_employer_gateway_call(
                    telegram_user_id=actor.id,
                    access_token=access_token,
                    operation=lambda token: self._employer_gateway.delete_document(
                        access_token=token,
                        employer_id=employer.id,
                        idempotency_key=idempotency_key,
                    ),
                )
                success_text = "Документ компании удалён."
                action_name = "employer_document_deleted"

            updated = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.get_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
            stats = (
                await self._safe_get_employer_statistics(
                    access_token=access_token,
                    employer_id=updated.id,
                )
                if updated is not None
                else None
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "employer delete file failed",
                extra={"telegram_user_id": actor.id, "target_kind": target_kind},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Готово",
            show_alert=False,
        )
        if updated is None:
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=self._build_employer_file_status_message(
                    title="Файл удалён",
                    status_line=f"✅ {success_text}",
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": action_name}

        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=f"✅ *{success_text}*\n\n"
            + self._build_employer_dashboard_message(
                first_name=actor.first_name,
                employer=updated,
                statistics=stats,
                created_now=False,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_employer_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": action_name}
