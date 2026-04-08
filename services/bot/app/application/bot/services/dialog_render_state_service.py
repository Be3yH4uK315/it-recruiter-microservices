from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.repositories.dialog_render_states import (
    DialogRenderStateRepository,
)


@dataclass(slots=True, frozen=True)
class DialogRenderStateView:
    telegram_user_id: int
    chat_id: int
    primary_message_id: int | None
    attachment_message_ids: list[int]


class DialogRenderStateService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = DialogRenderStateRepository(session)

    async def get_state(
        self,
        *,
        telegram_user_id: int,
    ) -> DialogRenderStateView | None:
        model = await self._repo.get_by_telegram_user_id(telegram_user_id)
        if model is None:
            return None

        return DialogRenderStateView(
            telegram_user_id=model.telegram_user_id,
            chat_id=model.chat_id,
            primary_message_id=model.primary_message_id,
            attachment_message_ids=self._normalize_message_ids(model.attachment_message_ids),
        )

    async def replace_state(
        self,
        *,
        telegram_user_id: int,
        chat_id: int,
        primary_message_id: int | None,
        attachment_message_ids: list[int],
    ) -> DialogRenderStateView:
        normalized_attachments = self._normalize_message_ids(attachment_message_ids)
        model = await self._repo.replace_state(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            primary_message_id=primary_message_id,
            attachment_message_ids=normalized_attachments,
        )
        return DialogRenderStateView(
            telegram_user_id=model.telegram_user_id,
            chat_id=model.chat_id,
            primary_message_id=model.primary_message_id,
            attachment_message_ids=self._normalize_message_ids(model.attachment_message_ids),
        )

    async def clear_state(
        self,
        *,
        telegram_user_id: int,
    ) -> None:
        await self._repo.clear_state(telegram_user_id=telegram_user_id)

    @staticmethod
    def _normalize_message_ids(raw_ids: list[int] | None) -> list[int]:
        normalized: list[int] = []
        for raw_id in raw_ids or []:
            try:
                message_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if message_id > 0 and message_id not in normalized:
                normalized.append(message_id)
        return normalized
