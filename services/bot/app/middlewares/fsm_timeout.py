import logging
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, Optional
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

class FSMTimeoutMiddleware(BaseMiddleware):
    """Middleware для очистки FSM после таймаута."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: Optional[User] = data.get("event_from_user")
        
        state: Optional[FSMContext] = data.get('state')
        if state:
            state_data: Dict[str, Any] = await state.get_data()
            last_activity: Optional[str] = state_data.get('last_activity')
            if last_activity and datetime.now() - datetime.fromisoformat(last_activity) > timedelta(minutes=30):
                await state.clear()
                user_id = user.id if user else "unknown"
                logger.info(f"Cleared FSM state for user {user_id} due to timeout")
                if hasattr(event, "message") and event.message:
                     try:
                         await event.message.answer("Сессия истекла. Начните заново с /start или /profile.")
                     except: pass
                elif hasattr(event, "answer"):
                     try:
                         await event.answer("Сессия истекла", show_alert=True)
                     except: pass
        if state:
            await state.update_data(last_activity=datetime.now().isoformat())
            
        return await handler(event, data)
