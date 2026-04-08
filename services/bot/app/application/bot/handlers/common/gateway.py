from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from app.application.common.contracts import CandidateStatisticsView, EmployerStatisticsView
from app.application.common.gateway_errors import (
    CandidateGatewayConflictError,
    CandidateGatewayForbiddenError,
    CandidateGatewayProtocolError,
    CandidateGatewayRateLimitedError,
    CandidateGatewayUnauthorizedError,
    CandidateGatewayUnavailableError,
    CandidateGatewayValidationError,
    EmployerGatewayConflictError,
    EmployerGatewayForbiddenError,
    EmployerGatewayNotFoundError,
    EmployerGatewayProtocolError,
    EmployerGatewayRateLimitedError,
    EmployerGatewayUnauthorizedError,
    EmployerGatewayUnavailableError,
    EmployerGatewayValidationError,
)
from app.application.observability.logging import get_logger
from app.application.observability.metrics import mark_callback_failed
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser

logger = get_logger(__name__)
ReturnT = TypeVar("ReturnT")


class GatewayUtilsMixin:
    def _build_gateway_feedback_message(
        self,
        *,
        gateway_label: str,
        title: str,
        status_line: str,
        details: list[str] | None = None,
    ) -> str:
        return self._build_status_screen(
            section_path=f"Системные сообщения · {gateway_label}",
            title=title,
            status_line=status_line,
            details=details,
        )

    async def _send_gateway_feedback(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
        as_attachment: bool = False,
        parse_mode: str | None = "Markdown",
    ) -> None:
        if as_attachment and hasattr(self._telegram_client, "send_attachment_message"):
            await self._telegram_client.send_attachment_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return

        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    async def _run_candidate_gateway_call(
        self,
        *,
        telegram_user_id: int,
        operation: Callable[[str], Awaitable[ReturnT]],
        access_token: str | None = None,
    ) -> ReturnT:
        token = access_token or await self._auth_session_service.get_valid_access_token(
            telegram_user_id=telegram_user_id
        )
        if token is None:
            raise CandidateGatewayUnauthorizedError("candidate access token is missing")

        try:
            return await operation(token)
        except CandidateGatewayUnauthorizedError:
            refreshed = await self._auth_session_service.force_refresh_access_token(
                telegram_user_id=telegram_user_id
            )
            if refreshed is None:
                raise
            return await operation(refreshed)

    async def _run_employer_gateway_call(
        self,
        *,
        telegram_user_id: int,
        operation: Callable[[str], Awaitable[ReturnT]],
        access_token: str | None = None,
    ) -> ReturnT:
        token = access_token or await self._auth_session_service.get_valid_access_token(
            telegram_user_id=telegram_user_id
        )
        if token is None:
            raise EmployerGatewayUnauthorizedError("employer access token is missing")

        try:
            return await operation(token)
        except EmployerGatewayUnauthorizedError:
            refreshed = await self._auth_session_service.force_refresh_access_token(
                telegram_user_id=telegram_user_id
            )
            if refreshed is None:
                raise
            return await operation(refreshed)

    def _log_flow_event(
        self,
        event: str,
        *,
        telegram_user_id: int | None,
        role_context: str | None = None,
        state_key: str | None = None,
        action_type: str | None = None,
        extra: dict | None = None,
    ) -> None:
        payload = {
            "telegram_user_id": telegram_user_id,
            "role_context": role_context,
            "state_key": state_key,
            "action_type": action_type,
        }
        if extra:
            payload.update(extra)
        logger.info(event, extra=payload)

    async def _safe_get_candidate_statistics(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
    ) -> CandidateStatisticsView | None:
        try:
            return await self._candidate_gateway.get_statistics(
                access_token=access_token,
                candidate_id=candidate_id,
            )
        except Exception:
            logger.warning(
                "candidate statistics unavailable",
                extra={"candidate_id": str(candidate_id)},
            )
            return None

    async def _safe_get_employer_statistics(
        self,
        *,
        access_token: str,
        employer_id: UUID,
    ) -> EmployerStatisticsView | None:
        try:
            return await self._employer_gateway.get_statistics(
                access_token=access_token,
                employer_id=employer_id,
            )
        except Exception:
            logger.warning(
                "employer statistics unavailable",
                extra={"employer_id": str(employer_id)},
            )
            return None

    async def _handle_candidate_gateway_error(
        self,
        *,
        chat_id: int,
        exc: Exception,
        fallback_text: str = "Сервис кандидатов временно недоступен. Попробуй позже.",
        as_attachment: bool = False,
    ) -> None:
        if isinstance(exc, CandidateGatewayUnauthorizedError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Кандидаты",
                    title="Сессия истекла",
                    status_line="⚠️ Сессия устарела.",
                    details=["Нажми `/start`, чтобы выбрать роль заново."],
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, CandidateGatewayForbiddenError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Кандидаты",
                    title="Недостаточно прав",
                    status_line="⚠️ Недостаточно прав для этого действия.",
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, CandidateGatewayConflictError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Кандидаты",
                    title="Данные изменились",
                    status_line="⚠️ Данные кандидата изменились.",
                    details=["Обнови меню и попробуй снова."],
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, CandidateGatewayValidationError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Кандидаты",
                    title="Ошибка в данных",
                    status_line="⚠️ Проверь введённые данные кандидата.",
                    details=["После этого попробуй ещё раз."],
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, CandidateGatewayRateLimitedError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Кандидаты",
                    title="Слишком много запросов",
                    status_line="⚠️ Слишком много запросов к сервису кандидатов.",
                    details=["Подожди немного и повтори."],
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, CandidateGatewayUnavailableError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Кандидаты",
                    title="Сервис временно недоступен",
                    status_line="⚠️ Сервис кандидатов временно недоступен.",
                    details=["Попробуй позже."],
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, CandidateGatewayProtocolError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Кандидаты",
                    title="Некорректный ответ сервиса",
                    status_line="⚠️ Сервис кандидатов вернул некорректный ответ.",
                    details=["Попробуй позже."],
                ),
                as_attachment=as_attachment,
            )
            return

        await self._send_gateway_feedback(
            chat_id=chat_id,
            text=fallback_text,
            as_attachment=as_attachment,
        )

    async def _handle_employer_gateway_error(
        self,
        *,
        chat_id: int,
        exc: Exception,
        fallback_text: str = "Сервис работодателей временно недоступен. Попробуй позже.",
        as_attachment: bool = False,
    ) -> None:
        if isinstance(exc, EmployerGatewayUnauthorizedError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Работодатели",
                    title="Сессия истекла",
                    status_line="⚠️ Сессия устарела.",
                    details=["Нажми `/start`, чтобы выбрать роль заново."],
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, EmployerGatewayForbiddenError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Работодатели",
                    title="Недостаточно прав",
                    status_line="⚠️ Недостаточно прав для этого действия.",
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, EmployerGatewayConflictError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Работодатели",
                    title="Данные изменились",
                    status_line="⚠️ Данные поиска или профиля изменились.",
                    details=["Обнови меню и попробуй снова."],
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, EmployerGatewayValidationError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Работодатели",
                    title="Ошибка в данных",
                    status_line="⚠️ Часть полей не прошла валидацию.",
                    details=["Проверь параметры запроса."],
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, EmployerGatewayRateLimitedError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Работодатели",
                    title="Слишком много запросов",
                    status_line="⚠️ Слишком много запросов к сервису работодателей.",
                    details=["Подожди немного и повтори."],
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, EmployerGatewayNotFoundError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Работодатели",
                    title="Ничего не найдено",
                    status_line="⚠️ Запрос или сущность не найдены.",
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, EmployerGatewayUnavailableError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Работодатели",
                    title="Сервис временно недоступен",
                    status_line="⚠️ Сервис работодателей временно недоступен.",
                    details=["Попробуй позже."],
                ),
                as_attachment=as_attachment,
            )
            return

        if isinstance(exc, EmployerGatewayProtocolError):
            await self._send_gateway_feedback(
                chat_id=chat_id,
                text=self._build_gateway_feedback_message(
                    gateway_label="Работодатели",
                    title="Некорректный ответ сервиса",
                    status_line="⚠️ Сервис работодателей вернул некорректный ответ.",
                    details=["Попробуй позже."],
                ),
                as_attachment=as_attachment,
            )
            return

        await self._send_gateway_feedback(
            chat_id=chat_id,
            text=fallback_text,
            as_attachment=as_attachment,
        )

    async def _answer_callback_and_handle_gateway_error(
        self,
        *,
        callback: TelegramCallbackQuery,
        actor: TelegramUser,
        exc: Exception,
        gateway_type: str,
        callback_text: str = "Операция недоступна",
    ) -> None:
        mark_callback_failed("gateway_error")
        self._log_flow_event(
            "callback_gateway_error",
            telegram_user_id=actor.id,
            action_type=gateway_type,
            extra={"callback_id": callback.id, "error_type": exc.__class__.__name__},
        )
        try:
            await self._telegram_client.answer_callback_query(
                callback_query_id=callback.id,
                text=callback_text,
                show_alert=False,
            )
        except Exception:
            logger.warning(
                "failed to answer callback query while handling gateway error",
                extra={
                    "telegram_user_id": actor.id,
                    "gateway_type": gateway_type,
                },
            )

        chat_id = self._resolve_chat_id(callback, actor)

        if gateway_type == "candidate":
            await self._handle_candidate_gateway_error(
                chat_id=chat_id,
                exc=exc,
                as_attachment=True,
            )
            return

        await self._handle_employer_gateway_error(
            chat_id=chat_id,
            exc=exc,
            as_attachment=True,
        )

    async def _send_retry_action_if_temporarily_unavailable(
        self,
        *,
        chat_id: int,
        telegram_user_id: int,
        exc: Exception,
        gateway_type: str,
        retry_action: str,
        retry_payload: dict,
    ) -> None:
        is_temporary = isinstance(
            exc,
            (
                CandidateGatewayUnavailableError,
                CandidateGatewayProtocolError,
                EmployerGatewayUnavailableError,
                EmployerGatewayProtocolError,
            ),
        )
        if not is_temporary:
            return

        retry_token = await self._create_callback_context(
            telegram_user_id=telegram_user_id,
            action_type=retry_action,
            payload=retry_payload,
        )
        await self._send_gateway_feedback(
            chat_id=chat_id,
            text=self._build_gateway_feedback_message(
                gateway_label="Системные действия",
                title="Можно повторить попытку",
                status_line="ℹ️ Можно попробовать ещё раз прямо сейчас.",
            ),
            reply_markup={
                "inline_keyboard": [
                    [{"text": "🔁 Повторить попытку", "callback_data": retry_token}]
                ]
            },
            as_attachment=True,
        )
        self._log_flow_event(
            "retry_action_suggested",
            telegram_user_id=telegram_user_id,
            action_type=retry_action,
            extra={"gateway_type": gateway_type},
        )

    async def _expired_session_callback(self, callback: TelegramCallbackQuery) -> None:
        await self._telegram_client.answer_callback_query(
            callback_query_id=callback.id,
            text="Сессия устарела. Нажми /start, чтобы обновить меню.",
            show_alert=True,
        )
