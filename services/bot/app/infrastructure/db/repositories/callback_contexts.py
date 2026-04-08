from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.bot import CallbackContextModel


class CallbackContextRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        token: str,
        telegram_user_id: int,
        action_type: str,
        payload: dict,
        expires_at: datetime,
    ) -> CallbackContextModel:
        model = CallbackContextModel(
            token=token,
            telegram_user_id=telegram_user_id,
            action_type=action_type,
            payload=payload,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.flush()
        return model

    async def get_active_for_user(
        self,
        *,
        token: str,
        telegram_user_id: int,
    ) -> CallbackContextModel | None:
        now = datetime.now(timezone.utc)

        stmt = select(CallbackContextModel).where(
            CallbackContextModel.token == token,
            CallbackContextModel.telegram_user_id == telegram_user_id,
            CallbackContextModel.consumed_at.is_(None),
            CallbackContextModel.expires_at > now,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def consume(
        self,
        *,
        model: CallbackContextModel,
    ) -> None:
        model.consumed_at = datetime.now(timezone.utc)
        await self._session.flush()
