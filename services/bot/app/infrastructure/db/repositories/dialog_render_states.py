from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.bot import DialogRenderStateModel


class DialogRenderStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_user_id(
        self,
        telegram_user_id: int,
    ) -> DialogRenderStateModel | None:
        stmt = select(DialogRenderStateModel).where(
            DialogRenderStateModel.telegram_user_id == telegram_user_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def replace_state(
        self,
        *,
        telegram_user_id: int,
        chat_id: int,
        primary_message_id: int | None,
        attachment_message_ids: list[int],
    ) -> DialogRenderStateModel:
        model = await self.get_by_telegram_user_id(telegram_user_id)
        if model is None:
            model = DialogRenderStateModel(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id,
                primary_message_id=primary_message_id,
                attachment_message_ids=list(attachment_message_ids),
            )
            self._session.add(model)
            await self._session.flush()
            return model

        model.chat_id = chat_id
        model.primary_message_id = primary_message_id
        model.attachment_message_ids = list(attachment_message_ids)
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

        await self._session.delete(model)
        await self._session.flush()
