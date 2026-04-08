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
    ) -> None:
        if isinstance(exc, CandidateGatewayUnauthorizedError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сессия устарела. Нажми /start, чтобы выбрать роль заново.",
            )
            return

        if isinstance(exc, CandidateGatewayForbiddenError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Недостаточно прав для этого действия.",
            )
            return

        if isinstance(exc, CandidateGatewayConflictError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Данные кандидата изменились. Обнови меню и попробуй снова.",
            )
            return

        if isinstance(exc, CandidateGatewayValidationError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Проверь введённые данные кандидата и попробуй ещё раз.",
            )
            return

        if isinstance(exc, CandidateGatewayRateLimitedError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Слишком много запросов к сервису кандидатов. Подожди немного и повтори.",
            )
            return

        if isinstance(exc, CandidateGatewayUnavailableError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сервис кандидатов временно недоступен. Попробуй позже.",
            )
            return

        if isinstance(exc, CandidateGatewayProtocolError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сервис кандидатов вернул некорректный ответ. Попробуй позже.",
            )
            return

        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=fallback_text,
        )

    async def _handle_employer_gateway_error(
        self,
        *,
        chat_id: int,
        exc: Exception,
        fallback_text: str = "Сервис работодателей временно недоступен. Попробуй позже.",
    ) -> None:
        if isinstance(exc, EmployerGatewayUnauthorizedError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сессия устарела. Нажми /start, чтобы выбрать роль заново.",
            )
            return

        if isinstance(exc, EmployerGatewayForbiddenError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Недостаточно прав для этого действия.",
            )
            return

        if isinstance(exc, EmployerGatewayConflictError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Данные поиска или профиля изменились. Обнови меню и попробуй снова.",
            )
            return

        if isinstance(exc, EmployerGatewayValidationError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Проверь параметры запроса: часть полей не прошла валидацию.",
            )
            return

        if isinstance(exc, EmployerGatewayRateLimitedError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Слишком много запросов к сервису работодателей. Подожди немного и повтори.",
            )
            return

        if isinstance(exc, EmployerGatewayNotFoundError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Запрос или сущность не найдены.",
            )
            return

        if isinstance(exc, EmployerGatewayUnavailableError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сервис работодателей временно недоступен. Попробуй позже.",
            )
            return

        if isinstance(exc, EmployerGatewayProtocolError):
            await self._telegram_client.send_message(
                chat_id=chat_id,
                text="Сервис работодателей вернул некорректный ответ. Попробуй позже.",
            )
            return

        await self._telegram_client.send_message(
            chat_id=chat_id,
            text=fallback_text,
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
            await self._handle_candidate_gateway_error(chat_id=chat_id, exc=exc)
            return

        await self._handle_employer_gateway_error(chat_id=chat_id, exc=exc)

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
        await self._telegram_client.send_message(
            chat_id=chat_id,
            text="Можно попробовать ещё раз прямо сейчас.",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "🔁 Повторить попытку", "callback_data": retry_token}]
                ]
            },
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
