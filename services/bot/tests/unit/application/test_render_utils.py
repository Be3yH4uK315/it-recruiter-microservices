from __future__ import annotations

import pytest

from app.application.bot.handlers.common.render import (
    RenderUtilsMixin,
    TELEGRAM_PHOTO_CAPTION_MAX_LEN,
)
from app.application.common.telegram_api import TelegramApiError
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser


class DummyTelegramClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self.primary_photos: list[dict] = []
        self.raise_photo = False

    async def send_message(self, **kwargs) -> None:
        self.sent_messages.append(kwargs)

    async def send_primary_photo(self, **kwargs) -> None:
        if self.raise_photo:
            raise TelegramApiError("photo failed")
        self.primary_photos.append(kwargs)


class RenderSut(RenderUtilsMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self.render_calls: list[dict] = []

    def _resolve_chat_id(self, callback: TelegramCallbackQuery, actor: TelegramUser) -> int:
        if callback.message is not None and callback.message.chat is not None:
            return int(callback.message.chat.id)
        return int(actor.id)

    async def _render_callback_screen(self, **kwargs) -> None:
        self.render_calls.append(kwargs)


def make_actor() -> TelegramUser:
    return TelegramUser.model_validate({"id": 100, "is_bot": False, "first_name": "User"})


def make_callback() -> TelegramCallbackQuery:
    return TelegramCallbackQuery.model_validate(
        {
            "id": "cb1",
            "from": {"id": 100, "is_bot": False, "first_name": "User"},
            "data": "x",
            "message": {
                "message_id": 10,
                "chat": {"id": 100, "type": "private"},
            },
        }
    )


@pytest.mark.asyncio
async def test_render_callback_screen_with_optional_photo_sends_primary_photo() -> None:
    sut = RenderSut()

    await sut._render_callback_screen_with_optional_photo(
        callback=make_callback(),
        actor=make_actor(),
        text="profile text",
        photo_url="https://example.com/avatar.jpg",
        reply_markup={"k": 1},
        parse_mode="Markdown",
    )

    assert sut._telegram_client.primary_photos == [
        {
            "chat_id": 100,
            "photo": "https://example.com/avatar.jpg",
            "caption": "profile text",
            "reply_markup": {"k": 1},
            "parse_mode": "Markdown",
        }
    ]
    assert sut.render_calls == []


@pytest.mark.asyncio
async def test_render_callback_screen_with_optional_photo_falls_back_for_long_caption() -> None:
    sut = RenderSut()

    await sut._render_callback_screen_with_optional_photo(
        callback=make_callback(),
        actor=make_actor(),
        text="x" * (TELEGRAM_PHOTO_CAPTION_MAX_LEN + 1),
        photo_url="https://example.com/avatar.jpg",
        reply_markup={"k": 1},
        parse_mode="Markdown",
    )

    assert sut._telegram_client.primary_photos == []
    assert len(sut.render_calls) == 1


@pytest.mark.asyncio
async def test_render_callback_screen_with_optional_photo_falls_back_when_photo_send_fails() -> None:
    sut = RenderSut()
    sut._telegram_client.raise_photo = True

    await sut._render_callback_screen_with_optional_photo(
        callback=make_callback(),
        actor=make_actor(),
        text="profile text",
        photo_url="https://example.com/avatar.jpg",
        reply_markup={"k": 1},
        parse_mode="Markdown",
    )

    assert sut._telegram_client.primary_photos == []
    assert len(sut.render_calls) == 1
