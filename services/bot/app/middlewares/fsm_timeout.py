import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject, User

logger = logging.getLogger(__name__)


class FSMTimeoutMiddleware(BaseMiddleware):
    """Middleware для очистки FSM после таймаута."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")

        state: FSMContext | None = data.get("state")
        if state:
            state_data: dict[str, Any] = await state.get_data()
            last_activity: str | None = state_data.get("last_activity")
            if last_activity and datetime.now() - datetime.fromisoformat(last_activity) > timedelta(
                minutes=30
            ):
                await state.clear()
                user_id = user.id if user else "unknown"
                logger.info(f"Cleared FSM state for user {user_id} due to timeout")
                if hasattr(event, "message") and event.message:
                    try:
                        await event.message.answer(
                            "Сессия истекла. Начните заново с /start или /profile."
                        )
                    except Exception:
                        pass
                elif hasattr(event, "answer"):
                    try:
                        await event.answer("Сессия истекла", show_alert=True)
                    except Exception:
                        pass
        if state:
            await state.update_data(last_activity=datetime.now().isoformat())

        return await handler(event, data)
