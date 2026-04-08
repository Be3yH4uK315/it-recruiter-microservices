from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.application.bot.handlers.common.entrypoint import EntrypointHandlersMixin
from app.application.bot.handlers.common.utils import CommonUtilsMixin
from app.schemas.telegram import TelegramCallbackQuery, TelegramMessage


@dataclass
class RateCheck:
    allowed: bool


@dataclass
class StateView:
    state_key: str | None
    role_context: str | None = None


class FakeRateLimitService:
    def __init__(self) -> None:
        self.message_allowed = True
        self.callback_allowed = True

    def check_message(self, *, telegram_user_id: int) -> RateCheck:
        return RateCheck(allowed=self.message_allowed)

    def check_callback(self, *, telegram_user_id: int) -> RateCheck:
        return RateCheck(allowed=self.callback_allowed)


class FakeTelegramClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self.answered_callbacks: list[dict] = []

    async def send_message(self, **kwargs) -> None:
        self.sent_messages.append(kwargs)

    async def answer_callback_query(self, **kwargs) -> None:
        self.answered_callbacks.append(kwargs)


class FakeConversationStateService:
    def __init__(self) -> None:
        self.current_state: StateView | None = None
        self.cleared_for: list[int] = []
        self.set_calls: list[dict] = []

    async def get_state(self, *, telegram_user_id: int) -> StateView | None:
        return self.current_state

    async def clear_state(self, *, telegram_user_id: int) -> None:
        self.cleared_for.append(telegram_user_id)

    async def set_state(
        self,
        *,
        telegram_user_id: int,
        role_context: str | None,
        state_key: str,
        payload: dict | None = None,
    ) -> StateView:
        self.set_calls.append(
            {
                "telegram_user_id": telegram_user_id,
                "role_context": role_context,
                "state_key": state_key,
                "payload": payload,
            }
        )
        self.current_state = StateView(state_key=state_key, role_context=role_context)
        return self.current_state


class FakeAuthSessionService:
    def __init__(self) -> None:
        self.logout_calls: list[int] = []

    async def logout(self, *, telegram_user_id: int) -> None:
        self.logout_calls.append(telegram_user_id)


class FakeEntrypoint(CommonUtilsMixin, EntrypointHandlersMixin):
    def __init__(self) -> None:
        self._rate_limit_service = FakeRateLimitService()
        self._telegram_client = FakeTelegramClient()
        self._conversation_state_service = FakeConversationStateService()
        self._auth_session_service = FakeAuthSessionService()
        self.dispatched_calls: list[tuple[str, dict]] = []
        self.force_draft_conflict = False

    def _log_flow_event(self, *_args, **_kwargs) -> None:
        return None

    def _build_draft_conflict_state_label(self, state_key: str) -> str:
        return f"label:{state_key}"

    async def _build_start_resume_draft_markup(self, *, telegram_user_id: int):
        return {"user": telegram_user_id}

    async def _send_role_selection(self, *, chat_id: int, actor) -> None:
        self.dispatched_calls.append(("_send_role_selection", {"chat_id": chat_id, "actor": actor}))

    async def _render_callback_screen(self, **kwargs) -> None:
        self.dispatched_calls.append(("_render_callback_screen", kwargs))

    async def _build_stateful_cancel_markup(self, telegram_user_id: int):
        return {"cancel_for": telegram_user_id}

    def _resolve_chat_id(self, callback: TelegramCallbackQuery, actor) -> int:
        if callback.message is not None and callback.message.chat is not None:
            return int(callback.message.chat.id)
        return int(actor.id)

    async def _resolve_and_consume_callback_context(
        self,
        *,
        callback_data: str,
        telegram_user_id: int,
    ):
        if callback_data == "expired":
            return None
        return SimpleNamespace(
            action_type=callback_data, payload={"telegram_user_id": telegram_user_id}
        )

    def _should_prompt_draft_conflict(self, *, state, action: str) -> bool:
        return self.force_draft_conflict

    def __getattr__(self, name: str):
        if name.startswith("_handle_"):

            async def _handler(**kwargs):
                self.dispatched_calls.append((name, kwargs))
                return {"status": "processed", "action": name}

            return _handler
        raise AttributeError(name)


def make_message(
    *, text: str | None, with_actor: bool = True, with_chat: bool = True
) -> TelegramMessage:
    payload: dict = {"message_id": 1, "text": text}
    if with_actor:
        payload["from"] = {"id": 100, "is_bot": False, "first_name": "User"}
    if with_chat:
        payload["chat"] = {"id": 100, "type": "private"}
    return TelegramMessage.model_validate(payload)


def make_callback(*, data: str | None, with_actor: bool = True) -> TelegramCallbackQuery:
    payload: dict = {"id": "cb-1", "data": data}
    if with_actor:
        payload["from"] = {"id": 100, "is_bot": False, "first_name": "User"}
    return TelegramCallbackQuery.model_validate(payload)


@pytest.mark.asyncio
async def test_handle_message_ignored_without_actor_or_chat() -> None:
    sut = FakeEntrypoint()
    result = await sut._handle_message(
        make_message(text="/start", with_actor=False, with_chat=True)
    )
    assert result["status"] == "ignored"


@pytest.mark.asyncio
async def test_handle_message_rate_limited() -> None:
    sut = FakeEntrypoint()
    sut._rate_limit_service.message_allowed = False

    result = await sut._handle_message(make_message(text="hello"))

    assert result == {"status": "processed", "action": "message_rate_limited"}
    assert len(sut._telegram_client.sent_messages) == 1


@pytest.mark.asyncio
async def test_handle_message_start_with_draft_prompt() -> None:
    sut = FakeEntrypoint()
    sut._conversation_state_service.current_state = StateView(
        state_key="candidate_registration_display_name"
    )

    result = await sut._handle_message(make_message(text="/start"))

    assert result["action"] == "start_with_draft_prompt"
    assert len(sut._telegram_client.sent_messages) == 1


@pytest.mark.asyncio
async def test_handle_message_start_without_state() -> None:
    sut = FakeEntrypoint()

    result = await sut._handle_message(make_message(text="/start"))

    assert result["action"] == "start"
    assert any(call[0] == "_send_role_selection" for call in sut.dispatched_calls)


@pytest.mark.asyncio
async def test_handle_message_logout() -> None:
    sut = FakeEntrypoint()

    result = await sut._handle_message(make_message(text="/logout"))

    assert result["action"] == "logout"
    assert sut._auth_session_service.logout_calls == [100]
    assert sut._conversation_state_service.cleared_for == [100]


@pytest.mark.asyncio
async def test_handle_message_help_cancel_stateful_and_fallback() -> None:
    sut = FakeEntrypoint()

    result_help = await sut._handle_message(make_message(text="/help"))
    assert result_help["action"] == "_handle_help_command"

    result_cancel = await sut._handle_message(make_message(text="/cancel"))
    assert result_cancel["action"] == "_handle_cancel_command"

    sut._conversation_state_service.current_state = StateView(
        state_key="candidate_edit_display_name"
    )
    result_stateful = await sut._handle_message(make_message(text="new value"))
    assert result_stateful["action"] == "_handle_stateful_message"

    sut._conversation_state_service.current_state = None
    result_fallback = await sut._handle_message(make_message(text="unknown"))
    assert result_fallback["action"] == "fallback_message"


@pytest.mark.asyncio
async def test_handle_callback_edge_cases() -> None:
    sut = FakeEntrypoint()

    ignored = await sut._handle_callback(make_callback(data="x", with_actor=False))
    assert ignored["status"] == "ignored"

    sut._rate_limit_service.callback_allowed = False
    limited = await sut._handle_callback(make_callback(data="x"))
    assert limited["action"] == "callback_rate_limited"

    sut._rate_limit_service.callback_allowed = True
    empty = await sut._handle_callback(make_callback(data=None))
    assert empty["reason"] == "empty_callback_data"

    expired = await sut._handle_callback(make_callback(data="expired"))
    assert expired["action"] == "expired_callback"


DISPATCH_ACTIONS = [
    "draft_conflict_continue",
    "draft_conflict_reset_and_go",
    "start_resume_continue",
    "start_resume_reset",
    "select_role",
    "candidate_menu_dashboard",
    "candidate_menu_profile",
    "candidate_menu_profile_edit_menu",
    "candidate_menu_stats",
    "candidate_menu_help",
    "candidate_menu_open_edit_section",
    "candidate_menu_open_files_section",
    "candidate_menu_open_contacts_section",
    "candidate_menu_switch_role",
    "candidate_menu_edit_display_name",
    "candidate_menu_edit_headline_role",
    "candidate_menu_edit_location",
    "candidate_menu_edit_about_me",
    "candidate_menu_edit_work_modes",
    "candidate_menu_edit_english_level",
    "candidate_menu_edit_status",
    "candidate_menu_edit_salary",
    "candidate_menu_edit_skills",
    "candidate_menu_edit_education",
    "candidate_menu_edit_experiences",
    "candidate_menu_edit_projects",
    "candidate_menu_edit_contacts_visibility",
    "candidate_menu_edit_contact_telegram",
    "candidate_menu_edit_contact_email",
    "candidate_menu_edit_contact_phone",
    "candidate_menu_upload_avatar",
    "candidate_menu_upload_resume",
    "candidate_menu_download_avatar",
    "candidate_menu_download_resume",
    "candidate_menu_delete_avatar",
    "candidate_menu_delete_resume",
    "candidate_menu_contact_requests",
    "candidate_contact_request_refresh",
    "candidate_contact_request_open",
    "candidate_contact_request_decision",
    "candidate_registration_continue",
    "employer_registration_continue",
    "stateful_input_cancel",
    "employer_menu_create_search",
    "employer_menu_edit_company",
    "employer_menu_edit_contact_telegram",
    "employer_menu_edit_contact_email",
    "employer_menu_edit_contact_phone",
    "employer_menu_edit_contact_website",
    "employer_menu_list_searches",
    "employer_menu_favorites",
    "employer_menu_unlocked_contacts",
    "employer_open_collection_candidate",
    "employer_menu_upload_avatar",
    "employer_menu_upload_document",
    "employer_menu_download_avatar",
    "employer_menu_download_document",
    "employer_menu_delete_avatar",
    "employer_menu_delete_document",
    "employer_menu_profile",
    "employer_menu_stats",
    "employer_menu_help",
    "employer_menu_dashboard",
    "employer_menu_open_edit_section",
    "employer_menu_open_files_section",
    "employer_menu_open_search_section",
    "employer_menu_continue_active_search",
    "employer_menu_switch_role",
    "employer_search_create_confirm",
    "employer_search_confirm_back",
    "employer_search_confirm_edit_step",
    "employer_search_wizard_skip",
    "employer_search_wizard_cancel",
    "employer_search_wizard_back",
    "candidate_choice_work_mode_toggle",
    "candidate_choice_work_modes_done",
    "candidate_choice_work_modes_clear",
    "candidate_choice_contacts_visibility",
    "candidate_choice_english_level",
    "candidate_choice_status",
    "employer_search_choice_work_mode_toggle",
    "employer_search_choice_work_modes_done",
    "employer_search_choice_english",
    "employer_open_search",
    "employer_search_decision",
    "employer_search_resume_download",
    "employer_search_pause",
    "employer_search_resume",
    "employer_search_close",
    "employer_request_contact_access",
    "employer_next_candidate",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("action", DISPATCH_ACTIONS)
async def test_handle_callback_dispatches_known_actions(action: str) -> None:
    sut = FakeEntrypoint()
    result = await sut._handle_callback(make_callback(data=action))
    assert result["status"] == "processed"


@pytest.mark.asyncio
async def test_handle_callback_unknown_action() -> None:
    sut = FakeEntrypoint()
    result = await sut._handle_callback(make_callback(data="unknown_action"))
    assert result == {"status": "ignored", "reason": "unknown_callback_action"}
