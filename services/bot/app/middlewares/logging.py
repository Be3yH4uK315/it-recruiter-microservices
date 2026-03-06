import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from app.core.messages import Messages

logger = logging.getLogger(__name__)


class CustomFormatter(logging.Formatter):
    """Custom formatter для логов."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "user_id"):
            record.user_id = "system"
        return super().format(record)


class LoggingMiddleware(BaseMiddleware):
    """Middleware для логирования сообщений и коллбеков с user_id."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        user_id = user.id if user else "unknown"
        data["user_id"] = user_id

        state: FSMContext = data.get("state")
        if state:
            try:
                await state.get_data()
            except Exception as e:
                logger.error(f"FSM state error for user {user_id}: {e}")
                await state.clear()
                if hasattr(event, "answer"):
                    await event.answer(Messages.Common.SESSION_TIMEOUT)
                return

        try:
            if isinstance(event, Message):
                text = event.text or event.caption or "Non-text message"
                logger.info(f"Message from user {user_id}: {text}", extra={"user_id": user_id})
            elif isinstance(event, CallbackQuery):
                callback_data = event.data
                logger.info(
                    f"Callback from user {user_id}: {callback_data}",
                    extra={"user_id": user_id},
                )
            else:
                logger.info(
                    f"Event from user {user_id}: {type(event)}",
                    extra={"user_id": user_id},
                )

            return await handler(event, data)
        except Exception as e:
            logger.error(
                f"Error handling event for user {user_id}: {e}",
                exc_info=True,
                extra={"user_id": user_id},
            )
            if hasattr(event, "answer"):
                await event.answer(Messages.Common.API_ERROR)
            raise
