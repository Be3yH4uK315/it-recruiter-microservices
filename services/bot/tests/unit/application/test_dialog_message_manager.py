from __future__ import annotations

import pytest

from app.application.bot.services.dialog_message_manager import DialogAwareTelegramClient
from app.application.bot.services.dialog_render_state_service import (
    DialogRenderStateService,
    DialogRenderStateView,
)
from app.schemas.telegram import TelegramCallbackQuery, TelegramMessage


class DummyBaseTelegramClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self.sent_documents: list[dict] = []
        self.sent_photos: list[dict] = []
        self.edited_messages: list[dict] = []
        self.deleted_messages: list[dict] = []
        self.next_message_id = 100

    @property
    def uses_placeholder_token(self) -> bool:
        return False

    async def send_message(self, **kwargs) -> dict:
        payload = {"message_id": self.next_message_id, "chat": {"id": kwargs["chat_id"]}}
        payload.update(kwargs)
        self.next_message_id += 1
        self.sent_messages.append(payload)
        return payload

    async def send_document(self, **kwargs) -> dict:
        payload = {"message_id": self.next_message_id, "chat": {"id": kwargs["chat_id"]}}
        payload.update(kwargs)
        self.next_message_id += 1
        self.sent_documents.append(payload)
        return payload

    async def send_photo(self, **kwargs) -> dict:
        payload = {"message_id": self.next_message_id, "chat": {"id": kwargs["chat_id"]}}
        payload.update(kwargs)
        self.next_message_id += 1
        self.sent_photos.append(payload)
        return payload

    async def edit_message_text(self, **kwargs) -> dict:
        self.edited_messages.append(kwargs)
        return {
            "message_id": kwargs["message_id"],
            "chat": {"id": kwargs["chat_id"]},
            "text": kwargs["text"],
        }

    async def delete_message(self, **kwargs) -> dict:
        self.deleted_messages.append(kwargs)
        return {"ok": True, "result": True}

    async def answer_callback_query(self, **kwargs) -> dict:
        return kwargs


class InMemoryDialogRenderStateService:
    def __init__(self) -> None:
        self.state_by_user: dict[int, DialogRenderStateView] = {}

    async def get_state(self, *, telegram_user_id: int) -> DialogRenderStateView | None:
        return self.state_by_user.get(telegram_user_id)

    async def replace_state(
        self,
        *,
        telegram_user_id: int,
        chat_id: int,
        primary_message_id: int | None,
        attachment_message_ids: list[int],
    ) -> DialogRenderStateView:
        view = DialogRenderStateView(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            primary_message_id=primary_message_id,
            attachment_message_ids=list(attachment_message_ids),
        )
        self.state_by_user[telegram_user_id] = view
        return view

    async def clear_state(self, *, telegram_user_id: int) -> None:
        self.state_by_user.pop(telegram_user_id, None)


def make_message(*, message_id: int, text: str) -> TelegramMessage:
    return TelegramMessage.model_validate(
        {
            "message_id": message_id,
            "from": {"id": 100, "is_bot": False, "first_name": "User"},
            "chat": {"id": 100, "type": "private"},
            "text": text,
        }
    )


def make_callback(*, message_id: int) -> TelegramCallbackQuery:
    return TelegramCallbackQuery.model_validate(
        {
            "id": "cb-1",
            "data": "action",
            "from": {"id": 100, "is_bot": False, "first_name": "User"},
            "message": {
                "message_id": message_id,
                "chat": {"id": 100, "type": "private"},
                "text": "old",
            },
        }
    )


@pytest.mark.asyncio
async def test_message_update_replaces_previous_primary_and_deletes_user_message() -> None:
    base_client = DummyBaseTelegramClient()
    state_service = InMemoryDialogRenderStateService()
    state_service.state_by_user[100] = DialogRenderStateView(
        telegram_user_id=100,
        chat_id=100,
        primary_message_id=55,
        attachment_message_ids=[56],
    )
    sut = DialogAwareTelegramClient(
        base_client=base_client,
        render_state_service=state_service,  # type: ignore[arg-type]
    )

    await sut.begin_message_update(message=make_message(message_id=10, text="input"))
    await sut.send_message(chat_id=100, text="first")
    await sut.send_message(chat_id=100, text="second")
    await sut.finalize_update()

    assert base_client.deleted_messages == [
        {"chat_id": 100, "message_id": 10},
        {"chat_id": 100, "message_id": 55},
        {"chat_id": 100, "message_id": 56},
        {"chat_id": 100, "message_id": 100},
    ]
    assert state_service.state_by_user[100].primary_message_id == 101
    assert state_service.state_by_user[100].attachment_message_ids == []


@pytest.mark.asyncio
async def test_callback_attachment_keeps_callback_message_as_primary() -> None:
    base_client = DummyBaseTelegramClient()
    state_service = InMemoryDialogRenderStateService()
    state_service.state_by_user[100] = DialogRenderStateView(
        telegram_user_id=100,
        chat_id=100,
        primary_message_id=77,
        attachment_message_ids=[78],
    )
    sut = DialogAwareTelegramClient(
        base_client=base_client,
        render_state_service=state_service,  # type: ignore[arg-type]
    )

    await sut.begin_callback_update(callback=make_callback(message_id=77))
    await sut.send_document(chat_id=100, document="https://example.com/resume.pdf")
    await sut.finalize_update()

    assert base_client.deleted_messages == [{"chat_id": 100, "message_id": 78}]
    assert state_service.state_by_user[100].primary_message_id == 77
    assert state_service.state_by_user[100].attachment_message_ids == [100]


@pytest.mark.asyncio
async def test_callback_attachment_message_keeps_callback_message_as_primary() -> None:
    base_client = DummyBaseTelegramClient()
    state_service = InMemoryDialogRenderStateService()
    state_service.state_by_user[100] = DialogRenderStateView(
        telegram_user_id=100,
        chat_id=100,
        primary_message_id=77,
        attachment_message_ids=[78],
    )
    sut = DialogAwareTelegramClient(
        base_client=base_client,
        render_state_service=state_service,  # type: ignore[arg-type]
    )

    await sut.begin_callback_update(callback=make_callback(message_id=77))
    await sut.send_attachment_message(chat_id=100, text="fallback link")
    await sut.finalize_update()

    assert base_client.deleted_messages == [{"chat_id": 100, "message_id": 78}]
    assert state_service.state_by_user[100].primary_message_id == 77
    assert state_service.state_by_user[100].attachment_message_ids == [100]
