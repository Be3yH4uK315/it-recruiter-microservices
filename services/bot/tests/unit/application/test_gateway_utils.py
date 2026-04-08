from __future__ import annotations

import pytest

from app.application.bot.handlers.common.gateway import GatewayUtilsMixin
from app.application.bot.ui.profile_message_mixins.shared import ProfileSharedMessagesMixin
from app.application.common.gateway_errors import (
    CandidateGatewayForbiddenError,
    CandidateGatewayUnavailableError,
    EmployerGatewayUnavailableError,
)
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser


class DummyTelegramClient:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.attachment_messages: list[dict] = []
        self.answered_callbacks: list[dict] = []

    async def send_message(self, **kwargs) -> None:
        self.messages.append(kwargs)

    async def send_attachment_message(self, **kwargs) -> None:
        self.attachment_messages.append(kwargs)

    async def answer_callback_query(self, **kwargs) -> None:
        self.answered_callbacks.append(kwargs)


class GatewaySut(GatewayUtilsMixin, ProfileSharedMessagesMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self.created_contexts: list[dict] = []
        self.logged_events: list[dict] = []

    async def _create_callback_context(
        self, *, telegram_user_id: int, action_type: str, payload: dict
    ) -> str:
        self.created_contexts.append(
            {
                "telegram_user_id": telegram_user_id,
                "action_type": action_type,
                "payload": payload,
            }
        )
        return "retry-token"

    def _resolve_chat_id(self, callback: TelegramCallbackQuery, actor: TelegramUser) -> int:
        return actor.id

    def _log_flow_event(self, event: str, **kwargs) -> None:
        self.logged_events.append({"event": event, **kwargs})


def make_actor() -> TelegramUser:
    return TelegramUser.model_validate({"id": 100, "is_bot": False, "first_name": "User"})


def make_callback() -> TelegramCallbackQuery:
    return TelegramCallbackQuery.model_validate(
        {
            "id": "cb-1",
            "data": "action",
            "from": {"id": 100, "is_bot": False, "first_name": "User"},
            "message": {"message_id": 10, "chat": {"id": 100, "type": "private"}},
        }
    )


@pytest.mark.asyncio
async def test_candidate_gateway_error_uses_primary_message_in_message_flow() -> None:
    sut = GatewaySut()

    await sut._handle_candidate_gateway_error(
        chat_id=100,
        exc=CandidateGatewayForbiddenError("forbidden"),
    )

    assert sut._telegram_client.messages == [
        {
            "chat_id": 100,
            "text": sut._build_gateway_feedback_message(
                gateway_label="Кандидаты",
                title="Недостаточно прав",
                status_line="⚠️ Недостаточно прав для этого действия.",
            ),
            "reply_markup": None,
            "parse_mode": "Markdown",
        }
    ]
    assert sut._telegram_client.attachment_messages == []


@pytest.mark.asyncio
async def test_callback_gateway_error_uses_attachment_message() -> None:
    sut = GatewaySut()

    await sut._answer_callback_and_handle_gateway_error(
        callback=make_callback(),
        actor=make_actor(),
        exc=CandidateGatewayUnavailableError("down"),
        gateway_type="candidate",
    )

    assert sut._telegram_client.answered_callbacks == [
        {
            "callback_query_id": "cb-1",
            "text": "Операция недоступна",
            "show_alert": False,
        }
    ]
    assert sut._telegram_client.attachment_messages == [
        {
            "chat_id": 100,
            "text": sut._build_gateway_feedback_message(
                gateway_label="Кандидаты",
                title="Сервис временно недоступен",
                status_line="⚠️ Сервис кандидатов временно недоступен.",
                details=["Попробуй позже."],
            ),
            "reply_markup": None,
            "parse_mode": "Markdown",
        }
    ]
    assert sut._telegram_client.messages == []


@pytest.mark.asyncio
async def test_retry_action_suggestion_uses_attachment_message() -> None:
    sut = GatewaySut()

    await sut._send_retry_action_if_temporarily_unavailable(
        chat_id=100,
        telegram_user_id=100,
        exc=EmployerGatewayUnavailableError("down"),
        gateway_type="employer",
        retry_action="retry_action",
        retry_payload={"page": 1},
    )

    assert sut.created_contexts == [
        {
            "telegram_user_id": 100,
            "action_type": "retry_action",
            "payload": {"page": 1},
        }
    ]
    assert sut._telegram_client.attachment_messages == [
        {
            "chat_id": 100,
            "text": sut._build_gateway_feedback_message(
                gateway_label="Системные действия",
                title="Можно повторить попытку",
                status_line="ℹ️ Можно попробовать ещё раз прямо сейчас.",
            ),
            "reply_markup": {
                "inline_keyboard": [[{"text": "🔁 Повторить попытку", "callback_data": "retry-token"}]]
            },
            "parse_mode": "Markdown",
        }
    ]
    assert sut._telegram_client.messages == []
