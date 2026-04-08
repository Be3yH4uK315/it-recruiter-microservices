from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.bot import ConversationStateModel


class ConversationStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_user_id(
        self,
        telegram_user_id: int,
    ) -> ConversationStateModel | None:
        stmt = select(ConversationStateModel).where(
            ConversationStateModel.telegram_user_id == telegram_user_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_state(
        self,
        *,
        telegram_user_id: int,
        role_context: str | None,
        state_key: str,
        payload: dict | None,
    ) -> ConversationStateModel:
        model = await self.get_by_telegram_user_id(telegram_user_id)
        if model is None:
            model = ConversationStateModel(
                telegram_user_id=telegram_user_id,
                role_context=role_context,
                state_key=state_key,
                payload=payload or {},
                state_version=1,
            )
            self._session.add(model)
            await self._session.flush()
            return model

        model.role_context = role_context
        model.state_key = state_key
        model.payload = payload or {}
        model.state_version += 1
        await self._session.flush()
        return model

    async def clear_state(
        self,
        *,
        telegram_user_id: int,
    ) -> None:
        model = await self.get_by_telegram_user_id(telegram_user_id)
        if model is None:
            return

        model.role_context = None
        model.state_key = None
        model.payload = None
        model.state_version += 1
        await self._session.flush()

    async def count_active_states(self) -> int:
        stmt = (
            select(func.count())
            .select_from(ConversationStateModel)
            .where(ConversationStateModel.state_key.is_not(None))
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)
