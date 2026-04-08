from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.bot import ProcessedUpdateModel, TelegramActorModel


class BotStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_update_processed(self, update_id: int) -> bool:
        stmt = select(ProcessedUpdateModel.update_id).where(
            ProcessedUpdateModel.update_id == update_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def mark_update_processed(
        self,
        *,
        update_id: int,
        telegram_user_id: int | None,
        update_type: str,
        status: str = "processed",
    ) -> None:
        now = datetime.now(timezone.utc)
        self._session.add(
            ProcessedUpdateModel(
                update_id=update_id,
                telegram_user_id=telegram_user_id,
                update_type=update_type,
                received_at=now,
                processed_at=now,
                status=status,
            )
        )

    async def upsert_actor(
        self,
        *,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
        is_bot: bool,
    ) -> None:
        actor = await self._session.get(TelegramActorModel, telegram_user_id)
        if actor is None:
            actor = TelegramActorModel(
                telegram_user_id=telegram_user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                is_bot=is_bot,
            )
            self._session.add(actor)
            return

        actor.username = username
        actor.first_name = first_name
        actor.last_name = last_name
        actor.language_code = language_code
        actor.is_bot = is_bot
