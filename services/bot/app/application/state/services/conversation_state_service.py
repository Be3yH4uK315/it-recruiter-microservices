from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.repositories.conversation_states import ConversationStateRepository
from app.infrastructure.observability.metrics import set_active_conversations


@dataclass(slots=True, frozen=True)
class ConversationStateView:
    telegram_user_id: int
    role_context: str | None
    state_key: str | None
    state_version: int
    payload: dict | None


class ConversationStateService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ConversationStateRepository(session)

    async def get_state(
        self,
        *,
        telegram_user_id: int,
    ) -> ConversationStateView | None:
        model = await self._repo.get_by_telegram_user_id(telegram_user_id)
        if model is None:
            return None

        return ConversationStateView(
            telegram_user_id=model.telegram_user_id,
            role_context=model.role_context,
            state_key=model.state_key,
            state_version=model.state_version,
            payload=model.payload,
        )

    async def set_state(
        self,
        *,
        telegram_user_id: int,
        role_context: str | None,
        state_key: str,
        payload: dict | None = None,
    ) -> ConversationStateView:
        model = await self._repo.set_state(
            telegram_user_id=telegram_user_id,
            role_context=role_context,
            state_key=state_key,
            payload=payload,
        )
        await self._refresh_active_conversations_metric()
        return ConversationStateView(
            telegram_user_id=model.telegram_user_id,
            role_context=model.role_context,
            state_key=model.state_key,
            state_version=model.state_version,
            payload=model.payload,
        )

    async def _refresh_active_conversations_metric(self) -> None:
        active_count = await self._repo.count_active_states()
        set_active_conversations(active_count)

    async def clear_state(
        self,
        *,
        telegram_user_id: int,
    ) -> None:
        await self._repo.clear_state(telegram_user_id=telegram_user_id)
        await self._refresh_active_conversations_metric()
