from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.application.bot.constants import (
    CONTACT_VISIBILITY_PUBLIC,
    STATE_CANDIDATE_EDIT_CONTACTS_VISIBILITY,
    STATE_CANDIDATE_EDIT_ENGLISH_LEVEL,
    STATE_CANDIDATE_EDIT_STATUS,
    STATE_CANDIDATE_EDIT_WORK_MODES,
)
from app.application.bot.handlers.common.callback_context import ResolvedCallbackContext
from app.application.bot.handlers.common.stateful_messages import StatefulMessageHandlersMixin
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser


@dataclass
class DummyState:
    state_key: str
    role_context: str | None = None
    payload: dict | None = None


class DummyTelegramClient:
    def __init__(self) -> None:
        self.answered: list[dict] = []
        self.sent_messages: list[dict] = []

    async def answer_callback_query(self, **kwargs) -> None:
        self.answered.append(kwargs)

    async def send_message(self, **kwargs) -> None:
        self.sent_messages.append(kwargs)


class DummyConversationStateService:
    def __init__(self, state: DummyState) -> None:
        self.state = state

    async def get_state(self, *, telegram_user_id: int):
        return self.state


class CandidateChoiceSut(StatefulMessageHandlersMixin):
    def __init__(self, state: DummyState) -> None:
        self._telegram_client = DummyTelegramClient()
        self._conversation_state_service = DummyConversationStateService(state)
        self.edit_calls: list[dict] = []

    async def _handle_candidate_edit_submit(self, **kwargs) -> dict:
        self.edit_calls.append(kwargs)
        return {"status": "processed", "action": "candidate_edit_forwarded"}

    def _resolve_chat_id(self, callback, actor) -> int:
        return actor.id


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
async def test_candidate_edit_work_modes_done_forwards_without_intermediate_message() -> None:
    sut = CandidateChoiceSut(
        DummyState(
            state_key=STATE_CANDIDATE_EDIT_WORK_MODES,
            payload={"selected_work_modes": ["remote", "hybrid"]},
        )
    )

    result = await sut._handle_candidate_choice_work_modes_done(
        callback=make_callback(),
        actor=make_actor(),
    )

    assert result["action"] == "candidate_edit_forwarded"
    assert sut._telegram_client.answered == [
        {
            "callback_query_id": "cb1",
            "text": "Сохраняю формат работы",
            "show_alert": False,
        }
    ]
    assert sut.edit_calls == [
        {
            "actor": make_actor(),
            "chat_id": 100,
            "field_name": "work_modes",
            "raw_value": ["remote", "hybrid"],
        }
    ]
    assert sut._telegram_client.sent_messages == []


@pytest.mark.asyncio
async def test_candidate_edit_contacts_visibility_forwards_without_intermediate_message() -> None:
    sut = CandidateChoiceSut(DummyState(state_key=STATE_CANDIDATE_EDIT_CONTACTS_VISIBILITY))

    result = await sut._handle_candidate_choice_contacts_visibility(
        callback=make_callback(),
        actor=make_actor(),
        context=ResolvedCallbackContext(
            action_type="candidate_choice_contacts_visibility",
            payload={"value": CONTACT_VISIBILITY_PUBLIC},
        ),
    )

    assert result["action"] == "candidate_edit_forwarded"
    assert sut._telegram_client.answered == [
        {
            "callback_query_id": "cb1",
            "text": "Сохраняю видимость контактов",
            "show_alert": False,
        }
    ]
    assert sut.edit_calls == [
        {
            "actor": make_actor(),
            "chat_id": 100,
            "field_name": "contacts_visibility",
            "raw_value": CONTACT_VISIBILITY_PUBLIC,
        }
    ]
    assert sut._telegram_client.sent_messages == []


@pytest.mark.asyncio
async def test_candidate_edit_english_level_forwards_without_intermediate_message() -> None:
    sut = CandidateChoiceSut(DummyState(state_key=STATE_CANDIDATE_EDIT_ENGLISH_LEVEL))

    result = await sut._handle_candidate_choice_english_level(
        callback=make_callback(),
        actor=make_actor(),
        context=ResolvedCallbackContext(
            action_type="candidate_choice_english_level",
            payload={"value": "b2"},
        ),
    )

    assert result["action"] == "candidate_edit_forwarded"
    assert sut._telegram_client.answered == [
        {
            "callback_query_id": "cb1",
            "text": "Сохраняю уровень английского",
            "show_alert": False,
        }
    ]
    assert sut.edit_calls == [
        {
            "actor": make_actor(),
            "chat_id": 100,
            "field_name": "english_level",
            "raw_value": "B2",
        }
    ]
    assert sut._telegram_client.sent_messages == []


@pytest.mark.asyncio
async def test_candidate_edit_status_forwards_without_intermediate_message() -> None:
    sut = CandidateChoiceSut(DummyState(state_key=STATE_CANDIDATE_EDIT_STATUS))

    result = await sut._handle_candidate_choice_status(
        callback=make_callback(),
        actor=make_actor(),
        context=ResolvedCallbackContext(
            action_type="candidate_choice_status",
            payload={"value": "hidden"},
        ),
    )

    assert result["action"] == "candidate_edit_forwarded"
    assert sut._telegram_client.answered == [
        {
            "callback_query_id": "cb1",
            "text": "Сохраняю статус",
            "show_alert": False,
        }
    ]
    assert sut.edit_calls == [
        {
            "actor": make_actor(),
            "chat_id": 100,
            "field_name": "status",
            "raw_value": "hidden",
        }
    ]
    assert sut._telegram_client.sent_messages == []
