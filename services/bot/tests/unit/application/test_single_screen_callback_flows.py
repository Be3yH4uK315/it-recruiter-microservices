from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.application.bot.constants import (
    ROLE_CANDIDATE,
    ROLE_EMPLOYER,
    STATE_CANDIDATE_FILE_AWAIT_AVATAR,
    STATE_CANDIDATE_FILE_AWAIT_RESUME,
    STATE_CANDIDATE_REG_WORK_MODES,
    STATE_EMPLOYER_FILE_AWAIT_DOCUMENT,
    STATE_EMPLOYER_REG_CONTACT_EMAIL,
)
from app.application.bot.handlers.common.bootstrap import BootstrapRegistrationHandlersMixin
from app.application.bot.handlers.common.entrypoint import EntrypointHandlersMixin
from app.application.bot.handlers.common.utils import CommonUtilsMixin
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser


class DummyTelegramClient:
    def __init__(self) -> None:
        self.answered_callbacks: list[dict] = []

    async def answer_callback_query(self, **kwargs):
        self.answered_callbacks.append(kwargs)


class DummyConversationStateService:
    def __init__(self) -> None:
        self.set_calls: list[dict] = []
        self.cleared_for: list[int] = []

    async def get_state(self, *, telegram_user_id: int):
        return None

    async def set_state(self, **kwargs):
        self.set_calls.append(kwargs)
        return SimpleNamespace(**kwargs)

    async def clear_state(self, *, telegram_user_id: int) -> None:
        self.cleared_for.append(telegram_user_id)


class DummyRateLimitService:
    def check_callback(self, *, telegram_user_id: int):
        return SimpleNamespace(allowed=True)


class EntrypointSut(CommonUtilsMixin, EntrypointHandlersMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self._conversation_state_service = DummyConversationStateService()
        self._rate_limit_service = DummyRateLimitService()
        self.render_calls: list[dict] = []

    def _log_flow_event(self, *_args, **_kwargs) -> None:
        return None

    async def _resolve_and_consume_callback_context(
        self, *, callback_data: str, telegram_user_id: int
    ):
        return SimpleNamespace(action_type=callback_data, payload={})

    def _should_prompt_draft_conflict(self, *, state, action: str) -> bool:
        return False

    async def _build_stateful_cancel_markup(self, telegram_user_id: int):
        return {"cancel_for": telegram_user_id}

    async def _render_callback_screen(self, **kwargs):
        self.render_calls.append(kwargs)


class BootstrapSut(CommonUtilsMixin, BootstrapRegistrationHandlersMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self._conversation_state_service = DummyConversationStateService()
        self.render_calls: list[dict] = []

    def _log_flow_event(self, *_args, **_kwargs) -> None:
        return None

    async def _render_callback_screen(self, **kwargs):
        self.render_calls.append(kwargs)

    async def _build_candidate_work_modes_selector_markup(self, **kwargs):
        return {"candidate_work_modes": kwargs}

    async def _build_stateful_cancel_markup(self, telegram_user_id: int):
        return {"cancel_for": telegram_user_id}

    async def _build_role_selection_markup(self, telegram_user_id: int):
        return {"role_for": telegram_user_id}


def make_callback(action: str) -> TelegramCallbackQuery:
    return TelegramCallbackQuery.model_validate(
        {
            "id": "cb-1",
            "data": action,
            "from": {"id": 100, "is_bot": False, "first_name": "User"},
            "message": {"message_id": 10, "chat": {"id": 100, "type": "private"}},
        }
    )


def make_actor() -> TelegramUser:
    return TelegramUser.model_validate({"id": 100, "is_bot": False, "first_name": "User"})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "expected_state", "expected_text"),
    [
        ("candidate_menu_upload_avatar", STATE_CANDIDATE_FILE_AWAIT_AVATAR, "Отправь фото"),
        ("candidate_menu_upload_resume", STATE_CANDIDATE_FILE_AWAIT_RESUME, "Отправь резюме"),
        ("employer_menu_upload_document", STATE_EMPLOYER_FILE_AWAIT_DOCUMENT, "Отправь документ компании"),
    ],
)
async def test_callback_upload_starts_render_in_place(
    action: str,
    expected_state: str,
    expected_text: str,
) -> None:
    sut = EntrypointSut()

    result = await sut._handle_callback(make_callback(action))

    assert result["status"] == "processed"
    assert sut._conversation_state_service.set_calls[-1]["state_key"] == expected_state
    assert expected_text in sut.render_calls[-1]["text"]


@pytest.mark.asyncio
async def test_candidate_registration_continue_renders_in_place() -> None:
    sut = BootstrapSut()

    result = await sut._handle_candidate_registration_continue(
        callback=make_callback("candidate_registration_continue"),
        actor=make_actor(),
        context=SimpleNamespace(payload={"continue": True}),
    )

    assert result["action"] == "candidate_registration_continue"
    assert sut._conversation_state_service.set_calls[-1]["state_key"] == STATE_CANDIDATE_REG_WORK_MODES
    assert "Выбери форматы работы" in sut.render_calls[-1]["text"]


@pytest.mark.asyncio
async def test_employer_registration_continue_renders_in_place() -> None:
    sut = BootstrapSut()

    result = await sut._handle_employer_registration_continue(
        callback=make_callback("employer_registration_continue"),
        actor=make_actor(),
        context=SimpleNamespace(payload={"continue": True}),
    )

    assert result["action"] == "employer_registration_continue"
    assert sut._conversation_state_service.set_calls[-1]["state_key"] == STATE_EMPLOYER_REG_CONTACT_EMAIL
    assert "email" in sut.render_calls[-1]["text"]


@pytest.mark.asyncio
async def test_switch_role_from_menu_renders_role_selection_in_place() -> None:
    sut = BootstrapSut()

    result = await sut._handle_switch_role_from_menu(
        callback=make_callback("candidate_menu_switch_role"),
        actor=make_actor(),
    )

    assert result["action"] == "switch_role_from_menu"
    assert sut._conversation_state_service.cleared_for == [100]
    assert "Выбери роль" in sut.render_calls[-1]["text"]
    assert sut.render_calls[-1]["reply_markup"] == {"role_for": 100}
