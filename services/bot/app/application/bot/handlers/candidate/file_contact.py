from __future__ import annotations

from uuid import UUID

from app.application.bot.constants import ROLE_CANDIDATE, STATE_CANDIDATE_FILE_AWAIT_AVATAR
from app.application.bot.handlers.common.callback_context import (
    ResolvedCallbackContext,
)
from app.application.candidate.services.file_flow_service import CandidateFileFlowError
from app.application.common.gateway_errors import CandidateGatewayError, EmployerGatewayError
from app.application.common.telegram_api import TelegramApiError
from app.application.observability.logging import get_logger
from app.application.observability.metrics import mark_file_upload
from app.application.state.services.conversation_state_service import ConversationStateView
from app.schemas.telegram import TelegramCallbackQuery, TelegramMessage, TelegramUser

logger = get_logger(__name__)


class CandidateFileContactHandlersMixin:
    def _build_candidate_file_status_message(
        self,
        *,
        title: str,
        status_line: str,
        details: list[str] | None = None,
    ) -> str:
        return self._build_status_screen(
            section_path="Кабинет кандидата · Файлы",
            title=title,
            status_line=status_line,
            details=details,
        )

    async def _handle_candidate_file_upload_state(
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
                text=self._build_candidate_file_status_message(
                    title="Сессия истекла",
                    status_line="⚠️ Сессия устарела.",
                    details=["Нажми `/start`, чтобы выбрать роль заново."],
                ),
                parse_mode="Markdown",
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
        except CandidateGatewayError as exc:
            logger.warning(
                "candidate file flow profile load failed",
                extra={"telegram_user_id": actor.id, "state_key": state.state_key},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "candidate_gateway_error"}

        if candidate is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=self._build_candidate_file_status_message(
                    title="Профиль не найден",
                    status_line="⚠️ Профиль кандидата не найден.",
                    details=["Нажми `/start`, чтобы начать заново."],
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "candidate_not_found"}

        try:
            if state.state_key == STATE_CANDIDATE_FILE_AWAIT_AVATAR:
                await self._candidate_file_flow_service.process_avatar_upload(
                    access_token=access_token,
                    telegram_user_id=actor.id,
                    candidate_id=candidate.id,
                    message=message,
                )
                success_text = "Аватар успешно обновлён."
                action_name = "candidate_avatar_uploaded"
            else:
                await self._candidate_file_flow_service.process_resume_upload(
                    access_token=access_token,
                    telegram_user_id=actor.id,
                    candidate_id=candidate.id,
                    message=message,
                )
                success_text = "Резюме успешно обновлено."
                action_name = "candidate_resume_uploaded"
        except CandidateFileFlowError as exc:
            kind = (
                "candidate_avatar"
                if state.state_key == STATE_CANDIDATE_FILE_AWAIT_AVATAR
                else "candidate_resume"
            )
            mark_file_upload(ROLE_CANDIDATE, kind, "validation_failed")
            await self._telegram_client.send_message(chat_id=chat_id, text=str(exc))
            return {"status": "processed", "action": "candidate_file_upload_validation_failed"}
        except CandidateGatewayError as exc:
            kind = (
                "candidate_avatar"
                if state.state_key == STATE_CANDIDATE_FILE_AWAIT_AVATAR
                else "candidate_resume"
            )
            mark_file_upload(ROLE_CANDIDATE, kind, "gateway_failed")
            logger.warning(
                "candidate file flow gateway failed",
                extra={"telegram_user_id": actor.id, "state_key": state.state_key},
                exc_info=exc,
            )
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "candidate_gateway_error"}
        except Exception as exc:
            kind = (
                "candidate_avatar"
                if state.state_key == STATE_CANDIDATE_FILE_AWAIT_AVATAR
                else "candidate_resume"
            )
            mark_file_upload(ROLE_CANDIDATE, kind, "failed")
            logger.warning(
                "candidate file flow failed",
                extra={"telegram_user_id": actor.id, "state_key": state.state_key},
                exc_info=exc,
            )
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=self._build_candidate_file_status_message(
                    title="Файл не обработан",
                    status_line="⚠️ Не удалось обработать файл.",
                    details=["Попробуй отправить его ещё раз."],
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "candidate_file_upload_failed"}
        mark_file_upload(
            ROLE_CANDIDATE,
            (
                "candidate_avatar"
                if state.state_key == STATE_CANDIDATE_FILE_AWAIT_AVATAR
                else "candidate_resume"
            ),
            "linked",
        )

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)

        try:
            refreshed = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.get_profile_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
        except CandidateGatewayError:
            refreshed = None
        if refreshed is None:
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=self._build_candidate_file_status_message(
                    title="Файл обновлён",
                    status_line=f"✅ {success_text}",
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": action_name}

        stats = await self._safe_get_candidate_statistics(
            access_token=access_token,
            candidate_id=refreshed.id,
        )
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=f"✅ *{success_text}*\n\n"
            + self._build_candidate_dashboard_message(
                first_name=actor.first_name,
                candidate=refreshed,
                statistics=stats,
                created_now=False,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": action_name}

    async def _handle_candidate_delete_file(
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
            candidate = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.get_profile_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
            if candidate is None:
                await self._telegram_client.answer_callback_query(
                    callback_query_id=callback.id,
                    text="Профиль кандидата не найден",
                    show_alert=True,
                )
                return {"status": "processed", "action": "candidate_not_found"}

            if target_kind == "avatar":
                idempotency_key = self._build_idempotency_key(
                    telegram_user_id=actor.id,
                    operation="candidate.avatar.delete",
                    resource_id=candidate.id,
                )
                await self._run_candidate_gateway_call(
                    telegram_user_id=actor.id,
                    access_token=access_token,
                    operation=lambda token: self._candidate_gateway.delete_avatar(
                        access_token=token,
                        candidate_id=candidate.id,
                        idempotency_key=idempotency_key,
                    ),
                )
                success_text = "Аватар удалён."
                action_name = "candidate_avatar_deleted"
            else:
                idempotency_key = self._build_idempotency_key(
                    telegram_user_id=actor.id,
                    operation="candidate.resume.delete",
                    resource_id=candidate.id,
                )
                await self._run_candidate_gateway_call(
                    telegram_user_id=actor.id,
                    access_token=access_token,
                    operation=lambda token: self._candidate_gateway.delete_resume(
                        access_token=token,
                        candidate_id=candidate.id,
                        idempotency_key=idempotency_key,
                    ),
                )
                success_text = "Резюме удалено."
                action_name = "candidate_resume_deleted"

            updated = await self._run_candidate_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._candidate_gateway.get_profile_by_telegram(
                    access_token=token,
                    telegram_id=actor.id,
                ),
            )
            stats = (
                await self._safe_get_candidate_statistics(
                    access_token=access_token,
                    candidate_id=updated.id,
                )
                if updated is not None
                else None
            )
        except CandidateGatewayError as exc:
            logger.warning(
                "candidate delete file failed",
                extra={"telegram_user_id": actor.id, "target_kind": target_kind},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="candidate",
            )
            return {"status": "processed", "action": "candidate_gateway_error"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Готово",
            show_alert=False,
        )
        if updated is None:
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=self._build_candidate_file_status_message(
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
            + self._build_candidate_dashboard_message(
                first_name=actor.first_name,
                candidate=updated,
                statistics=stats,
                created_now=False,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_dashboard_markup(actor.id),
        )
        return {"status": "processed", "action": action_name}

    async def _handle_candidate_download_file(
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
                "candidate download file load failed",
                extra={"telegram_user_id": actor.id, "target_kind": target_kind},
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

        download_url = (
            candidate.avatar_download_url
            if target_kind == "avatar"
            else candidate.resume_download_url
        )
        if not download_url:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Файл не загружен",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_download_file_missing"}

        chat_id = self._resolve_chat_id(callback, actor)
        try:
            if target_kind == "avatar":
                await self._telegram_client.send_photo(
                    chat_id=chat_id,
                    photo=download_url,
                    caption="Текущий аватар",
                )
                action_name = "candidate_avatar_downloaded"
            else:
                await self._telegram_client.send_document(
                    chat_id=chat_id,
                    document=download_url,
                    caption="Текущее резюме",
                )
                action_name = "candidate_resume_downloaded"
        except TelegramApiError:
            # fallback: send clickable link when Telegram can't fetch external URL
            await self._telegram_client.send_attachment_message(
                chat_id=chat_id,
                text=f"Ссылка на файл:\n{download_url}",
            )
            action_name = (
                "candidate_avatar_download_link_sent"
                if target_kind == "avatar"
                else "candidate_resume_download_link_sent"
            )

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Готово",
            show_alert=False,
        )
        return {"status": "processed", "action": action_name}

    async def _handle_candidate_contact_requests_list(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext | None = None,
    ) -> dict:
        requested_page = self._extract_page_number(context.payload if context is not None else None)
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        try:
            requests = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=(
                    lambda token: self._employer_gateway.list_candidate_pending_contact_requests(
                        access_token=token,
                        limit=50,
                    )
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "candidate pending contact requests list failed",
                extra={"telegram_user_id": actor.id},
                exc_info=exc,
            )
            await self._answer_callback_and_handle_gateway_error(
                callback=callback,
                actor=actor,
                exc=exc,
                gateway_type="employer",
            )
            return {"status": "processed", "action": "employer_gateway_error"}

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Запросы контактов",
            show_alert=False,
        )
        paged_requests, page, total_pages = self._paginate_items(
            requests,
            page=requested_page,
        )
        if not requests:
            await self._render_callback_screen(
                callback=callback,
                actor=actor,
                text=self._build_status_screen(
                    section_path="Кабинет кандидата · Запросы контактов",
                    title="Запросы контактов",
                    status_line="ℹ️ Сейчас нет ожидающих запросов на открытие контактов.",
                    details=["Если работодатель отправит новый запрос, он появится здесь."],
                ),
                parse_mode="Markdown",
                reply_markup=await self._build_candidate_contact_requests_list_markup(
                    telegram_user_id=actor.id,
                    requests=[],
                    page=1,
                    total_pages=1,
                ),
            )
            return {"status": "processed", "action": "candidate_contact_requests_empty"}

        await self._render_callback_screen(
            callback=callback,
            actor=actor,
            text=self._build_candidate_pending_contact_requests_message(
                paged_requests,
                page=page,
                total_pages=total_pages,
            ),
            parse_mode="Markdown",
            reply_markup=await self._build_candidate_contact_requests_list_markup(
                telegram_user_id=actor.id,
                requests=requests,
                page=page,
                total_pages=total_pages,
            ),
        )
        return {"status": "processed", "action": "candidate_contact_requests_list"}

    async def _handle_candidate_contact_request_open(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        request_id_raw = str(context.payload.get("request_id", "")).strip()
        try:
            request_id = UUID(request_id_raw)
        except (TypeError, ValueError):
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text="Некорректный ID запроса",
                show_alert=True,
            )
            return {"status": "processed", "action": "candidate_contact_request_open_invalid_id"}

        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Открываю запрос",
            show_alert=False,
        )
        return await self._open_candidate_contact_request_by_id(
            actor=actor,
            chat_id=self._resolve_chat_id(callback, actor),
            request_id=request_id,
        )

    async def _handle_candidate_contact_request_lookup(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        raw_request_id: str,
    ) -> dict:
        try:
            request_id = UUID(raw_request_id.strip())
        except (TypeError, ValueError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "Неверный формат ID. Пришли UUID запроса, например: "
                    "`11111111-2222-3333-4444-555555555555`"
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "candidate_contact_request_invalid_id"}

        return await self._open_candidate_contact_request_by_id(
            actor=actor,
            chat_id=chat_id,
            request_id=request_id,
        )

    async def _open_candidate_contact_request_by_id(
        self,
        *,
        actor: TelegramUser,
        chat_id: int,
        request_id: UUID,
    ) -> dict:
        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=self._build_status_screen(
                    section_path="Кабинет кандидата · Запросы контактов",
                    title="Сессия истекла",
                    status_line="⚠️ Сессия устарела.",
                    details=["Нажми `/start`, чтобы выбрать роль заново."],
                ),
                parse_mode="Markdown",
            )
            return {"status": "processed", "action": "session_expired"}

        try:
            details = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=(
                    lambda token: self._employer_gateway.get_contact_request_details_for_candidate(
                        access_token=token,
                        request_id=request_id,
                    )
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "candidate contact request lookup failed",
                extra={"telegram_user_id": actor.id, "request_id": str(request_id)},
                exc_info=exc,
            )
            await self._handle_employer_gateway_error(chat_id=chat_id, exc=exc)
            return {"status": "processed", "action": "employer_gateway_error"}

        status_value = details.status.strip().lower()
        if status_value != "pending":
            await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text=self._build_candidate_contact_request_details_message(details),
                parse_mode="Markdown",
                reply_markup=await self._build_candidate_contact_requests_list_markup(
                    telegram_user_id=actor.id,
                    requests=[],
                ),
            )
            return {"status": "processed", "action": "candidate_contact_request_not_pending"}

        approve_token = await self._create_callback_context(
            telegram_user_id=actor.id,
            action_type="candidate_contact_request_decision",
            payload={"request_id": str(details.id), "granted": True},
        )
        reject_token = await self._create_callback_context(
            telegram_user_id=actor.id,
            action_type="candidate_contact_request_decision",
            payload={"request_id": str(details.id), "granted": False},
        )

        await self._conversation_state_service.clear_state(telegram_user_id=actor.id)
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=self._build_candidate_contact_request_details_message(details),
            parse_mode="Markdown",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "✅ Одобрить доступ", "callback_data": approve_token}],
                    [{"text": "❌ Отклонить", "callback_data": reject_token}],
                ]
            },
        )
        return {"status": "processed", "action": "candidate_contact_request_details"}

    async def _handle_candidate_contact_request_decision(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        context: ResolvedCallbackContext,
    ) -> dict:
        request_id = UUID(str(context.payload.get("request_id")))
        granted_raw = context.payload.get("granted")
        if isinstance(granted_raw, bool):
            granted = granted_raw
        else:
            granted = str(granted_raw).strip().lower() in {"1", "true", "yes", "да"}

        access_token = await self._auth_session_service.get_valid_access_token(
            telegram_user_id=actor.id
        )
        if access_token is None:
            await self._expired_session_callback(callback)
            return {"status": "processed", "action": "session_expired"}

        try:
            idempotency_key = self._build_idempotency_key(
                telegram_user_id=actor.id,
                operation="contacts.request.candidate_response",
                resource_id=request_id,
            )
            result = await self._run_employer_gateway_call(
                telegram_user_id=actor.id,
                access_token=access_token,
                operation=lambda token: self._employer_gateway.respond_contact_request(
                    access_token=token,
                    request_id=request_id,
                    granted=granted,
                    idempotency_key=idempotency_key,
                ),
            )
        except EmployerGatewayError as exc:
            logger.warning(
                "candidate contact request decision failed",
                extra={
                    "telegram_user_id": actor.id,
                    "request_id": str(request_id),
                    "granted": granted,
                },
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
            text="Ответ отправлен",
            show_alert=False,
        )
        await self._telegram_client.send_message(
            chat_id=self._resolve_chat_id(callback, actor),
            text=self._build_candidate_contact_request_decision_message(result),
            parse_mode="Markdown",
        )
        return {"status": "processed", "action": "candidate_contact_request_decision"}
