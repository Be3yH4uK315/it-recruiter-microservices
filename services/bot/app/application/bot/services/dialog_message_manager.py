from __future__ import annotations

from dataclasses import dataclass, field

from app.application.bot.services.dialog_render_state_service import (
    DialogRenderStateService,
    DialogRenderStateView,
)
from app.application.common.telegram_api import TelegramApiError
from app.infrastructure.telegram.client import TelegramApiClient
from app.schemas.telegram import TelegramCallbackQuery, TelegramMessage


def _extract_message_id(payload: dict) -> int | None:
    raw_message_id = payload.get("message_id")
    try:
        message_id = int(raw_message_id)
    except (TypeError, ValueError):
        return None
    if message_id <= 0:
        return None
    return message_id


@dataclass(slots=True)
class DialogUpdateContext:
    telegram_user_id: int
    chat_id: int
    incoming_message_id: int | None
    callback_message_id: int | None
    previous_primary_message_id: int | None
    previous_attachment_message_ids: list[int]
    touched_render: bool = False
    current_primary_message_id: int | None = None
    current_attachment_message_ids: list[int] = field(default_factory=list)
    obsolete_sent_message_ids: set[int] = field(default_factory=set)

    def note_sent_text(self, message_id: int) -> None:
        self.touched_render = True
        if (
            self.current_primary_message_id is not None
            and self.current_primary_message_id != message_id
        ):
            self.obsolete_sent_message_ids.add(self.current_primary_message_id)
        self.current_primary_message_id = message_id
        self.current_attachment_message_ids = [
            tracked_id
            for tracked_id in self.current_attachment_message_ids
            if tracked_id != message_id
        ]

    def note_sent_attachment(self, message_id: int) -> None:
        self.touched_render = True
        if message_id == self.current_primary_message_id:
            return
        if message_id not in self.current_attachment_message_ids:
            self.current_attachment_message_ids.append(message_id)

    def note_edited_text(self, message_id: int) -> None:
        self.touched_render = True
        if (
            self.current_primary_message_id is not None
            and self.current_primary_message_id != message_id
        ):
            self.obsolete_sent_message_ids.add(self.current_primary_message_id)
        self.current_primary_message_id = message_id
        self.current_attachment_message_ids = [
            tracked_id
            for tracked_id in self.current_attachment_message_ids
            if tracked_id != message_id
        ]


class DialogAwareTelegramClient:
    def __init__(
        self,
        *,
        base_client: TelegramApiClient,
        render_state_service: DialogRenderStateService,
    ) -> None:
        self._base_client = base_client
        self._render_state_service = render_state_service
        self._current_context: DialogUpdateContext | None = None

    @property
    def uses_placeholder_token(self) -> bool:
        return self._base_client.uses_placeholder_token

    async def begin_message_update(self, *, message: TelegramMessage) -> None:
        if message.from_user is None or message.chat is None:
            self._current_context = None
            return

        previous_state = await self._render_state_service.get_state(
            telegram_user_id=message.from_user.id
        )
        self._current_context = self._build_context(
            telegram_user_id=message.from_user.id,
            chat_id=message.chat.id,
            incoming_message_id=message.message_id,
            callback_message_id=None,
            previous_state=previous_state,
        )

    async def begin_callback_update(self, *, callback: TelegramCallbackQuery) -> None:
        if callback.from_user is None:
            self._current_context = None
            return

        previous_state = await self._render_state_service.get_state(
            telegram_user_id=callback.from_user.id
        )
        callback_message_id: int | None = None
        chat_id = callback.from_user.id
        if callback.message is not None and callback.message.chat is not None:
            callback_message_id = callback.message.message_id
            chat_id = callback.message.chat.id

        self._current_context = self._build_context(
            telegram_user_id=callback.from_user.id,
            chat_id=chat_id,
            incoming_message_id=None,
            callback_message_id=callback_message_id,
            previous_state=previous_state,
        )

    async def finalize_update(self) -> None:
        context = self._current_context
        self._current_context = None
        if context is None or not context.touched_render:
            return

        desired_primary_message_id = context.current_primary_message_id
        if desired_primary_message_id is None and context.callback_message_id is not None:
            desired_primary_message_id = context.callback_message_id

        desired_attachment_message_ids = [
            message_id
            for message_id in context.current_attachment_message_ids
            if message_id != desired_primary_message_id
        ]

        previous_message_ids = set(context.previous_attachment_message_ids)
        if context.previous_primary_message_id is not None:
            previous_message_ids.add(context.previous_primary_message_id)

        desired_message_ids = set(desired_attachment_message_ids)
        if desired_primary_message_id is not None:
            desired_message_ids.add(desired_primary_message_id)

        delete_message_ids = previous_message_ids.difference(desired_message_ids)
        delete_message_ids.update(
            message_id
            for message_id in context.obsolete_sent_message_ids
            if message_id not in desired_message_ids
        )

        if (
            context.incoming_message_id is not None
            and context.incoming_message_id not in desired_message_ids
        ):
            delete_message_ids.add(context.incoming_message_id)

        for message_id in sorted(delete_message_ids):
            await self._delete_message_safely(chat_id=context.chat_id, message_id=message_id)

        if desired_primary_message_id is None and not desired_attachment_message_ids:
            await self._render_state_service.clear_state(
                telegram_user_id=context.telegram_user_id
            )
            return

        await self._render_state_service.replace_state(
            telegram_user_id=context.telegram_user_id,
            chat_id=context.chat_id,
            primary_message_id=desired_primary_message_id,
            attachment_message_ids=desired_attachment_message_ids,
        )

    def discard_update(self) -> None:
        self._current_context = None

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        payload = await self._base_client.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        self._track_sent_text(payload)
        return payload

    async def send_photo(
        self,
        *,
        chat_id: int,
        photo: str,
        caption: str | None = None,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        payload = await self._base_client.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        self._track_sent_attachment(payload)
        return payload

    async def send_document(
        self,
        *,
        chat_id: int,
        document: str,
        caption: str | None = None,
    ) -> dict:
        payload = await self._base_client.send_document(
            chat_id=chat_id,
            document=document,
            caption=caption,
        )
        self._track_sent_attachment(payload)
        return payload

    async def edit_message_text(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        payload = await self._base_client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        context = self._current_context
        if context is not None and message_id > 0:
            context.note_edited_text(message_id)
        return payload

    async def delete_message(
        self,
        *,
        chat_id: int,
        message_id: int,
    ) -> dict:
        return await self._base_client.delete_message(chat_id=chat_id, message_id=message_id)

    async def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> dict:
        return await self._base_client.answer_callback_query(
            callback_query_id=callback_query_id,
            text=text,
            show_alert=show_alert,
        )

    async def get_file(self, *, file_id: str):
        return await self._base_client.get_file(file_id=file_id)

    async def download_file_bytes(self, *, file_path: str) -> bytes:
        return await self._base_client.download_file_bytes(file_path=file_path)

    @staticmethod
    def _build_context(
        *,
        telegram_user_id: int,
        chat_id: int,
        incoming_message_id: int | None,
        callback_message_id: int | None,
        previous_state: DialogRenderStateView | None,
    ) -> DialogUpdateContext:
        return DialogUpdateContext(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            incoming_message_id=incoming_message_id,
            callback_message_id=callback_message_id,
            previous_primary_message_id=(
                previous_state.primary_message_id if previous_state is not None else None
            ),
            previous_attachment_message_ids=(
                list(previous_state.attachment_message_ids)
                if previous_state is not None
                else []
            ),
        )

    def _track_sent_text(self, payload: dict) -> None:
        message_id = _extract_message_id(payload)
        if message_id is None or self._current_context is None:
            return
        self._current_context.note_sent_text(message_id)

    def _track_sent_attachment(self, payload: dict) -> None:
        message_id = _extract_message_id(payload)
        if message_id is None or self._current_context is None:
            return
        self._current_context.note_sent_attachment(message_id)

    async def _delete_message_safely(self, *, chat_id: int, message_id: int) -> None:
        try:
            await self._base_client.delete_message(chat_id=chat_id, message_id=message_id)
        except TelegramApiError:
            return
