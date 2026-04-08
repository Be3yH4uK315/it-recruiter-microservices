from __future__ import annotations

import httpx
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


class ResponseTextAsyncClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    async def post(self, url: str, **_kwargs):
        request = httpx.Request("POST", url)
        raise httpx.HTTPStatusError("telegram error", request=request, response=self.response)

    async def get(self, url: str, **_kwargs):
        raise AssertionError("unexpected get call")


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


def test_convert_markdown_to_markdown_v2_preserves_basic_formatting() -> None:
    converted = TelegramApiClient._convert_markdown_to_markdown_v2(
        "🧭 *Мастер поиска*\n\nВведи `2-5` и скобки (test)."
    )

    assert converted == "🧭 *Мастер поиска*\n\nВведи `2-5` и скобки \\(test\\)\\."


def test_convert_markdown_to_markdown_v2_handles_escaped_legacy_chars() -> None:
    converted = TelegramApiClient._convert_markdown_to_markdown_v2(
        "Имя: Python\\_\\[Lead\\] и путь \\\\server"
    )

    assert converted == "Имя: Python\\_\\[Lead\\] и путь \\\\server"


@pytest.mark.asyncio
async def test_answer_callback_query_ignores_expired_query_error() -> None:
    response = httpx.Response(
        400,
        json={
            "ok": False,
            "error_code": 400,
            "description": "Bad Request: query is too old and response timeout expired or query ID is invalid",
        },
    )
    client = TelegramApiClient(
        client=ResponseTextAsyncClient(response),
        base_url="https://api.telegram.org",
        bot_token="123:realistic-token",
    )

    result = await client.answer_callback_query(callback_query_id="cb-1", text="ok")

    assert result == {}
