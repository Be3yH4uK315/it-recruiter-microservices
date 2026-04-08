from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.bot import TelegramActorModel


class TelegramActorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self,
        *,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
        is_bot: bool,
    ) -> TelegramActorModel:
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
            await self._session.flush()
            return actor

        actor.username = username
        actor.first_name = first_name
        actor.last_name = last_name
        actor.language_code = language_code
        actor.is_bot = is_bot
        await self._session.flush()
        return actor
