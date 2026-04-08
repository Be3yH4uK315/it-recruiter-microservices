from __future__ import annotations

import pytest

from app.infrastructure.telegram.client import TelegramApiClient


class DummyAsyncClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def post(self, url: str, **_kwargs):
        self.calls.append(("post", url))
        raise AssertionError("network call must not happen for placeholder telegram token")

    async def get(self, url: str, **_kwargs):
        self.calls.append(("get", url))
        raise AssertionError("network call must not happen for placeholder telegram token")


@pytest.mark.asyncio
async def test_placeholder_token_short_circuits_send_message() -> None:
    http_client = DummyAsyncClient()
    client = TelegramApiClient(
        client=http_client,
        base_url="https://api.telegram.org",
        bot_token="change-me-telegram-bot-token",
    )

    result = await client.send_message(chat_id=123, text="hello")

    assert result["chat"]["id"] == 123
    assert result["text"] == "hello"
    assert http_client.calls == []


@pytest.mark.asyncio
async def test_placeholder_token_short_circuits_answer_callback_query() -> None:
    http_client = DummyAsyncClient()
    client = TelegramApiClient(
        client=http_client,
        base_url="https://api.telegram.org",
        bot_token="change-me-telegram-bot-token",
    )

    result = await client.answer_callback_query(
        callback_query_id="cb-1",
        text="ok",
        show_alert=False,
    )

    assert result == {"callback_query_id": "cb-1"}
    assert http_client.calls == []


@pytest.mark.asyncio
async def test_placeholder_token_short_circuits_delete_message() -> None:
    http_client = DummyAsyncClient()
    client = TelegramApiClient(
        client=http_client,
        base_url="https://api.telegram.org",
        bot_token="change-me-telegram-bot-token",
    )

    result = await client.delete_message(chat_id=123, message_id=7)

    assert result == {"ok": True, "result": True}
    assert http_client.calls == []
