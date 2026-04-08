from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.application.bot.constants import (
    ROLE_CANDIDATE,
    ROLE_EMPLOYER,
    STATE_CANDIDATE_FILE_AWAIT_AVATAR,
)
from app.application.bot.handlers.common.callback_context import ResolvedCallbackContext
from app.application.bot.handlers.common.commands import CommandHandlersMixin
from app.application.bot.handlers.common.recovery import RecoveryHandlersMixin
from app.application.bot.services.update_router import UpdateRouterService
from app.schemas.telegram import TelegramCallbackQuery, TelegramUpdate, TelegramUser


class DummyTelegramClient:
    def __init__(self) -> None:
        self.answers: list[dict] = []
        self.messages: list[dict] = []
        self.edits: list[dict] = []

    async def answer_callback_query(self, **kwargs):
        self.answers.append(kwargs)

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)


class DummyAuthSessionService:
    def __init__(self) -> None:
        self.active_role: str | None = None
        self.login_calls: list[dict] = []

    async def login_via_bot(self, **kwargs):
        self.login_calls.append(kwargs)

    async def get_active_role(self, *, telegram_user_id: int):
        return self.active_role


class DummyConversationStateService:
    def __init__(self) -> None:
        self.state = None
        self.cleared: list[int] = []

    async def get_state(self, *, telegram_user_id: int):
        return self.state

    async def clear_state(self, *, telegram_user_id: int):
        self.cleared.append(telegram_user_id)


class CommandSut(CommandHandlersMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self._auth_session_service = DummyAuthSessionService()
        self._conversation_state_service = DummyConversationStateService()
        self.bootstrap_calls: list[dict] = []
        self.flow_events: list[dict] = []

    async def _bootstrap_role(self, **kwargs):
        self.bootstrap_calls.append(kwargs)

    def _resolve_chat_id(self, callback, actor):
        return callback.message.chat.id if callback.message and callback.message.chat else actor.id

    def _log_flow_event(self, event_name: str, **kwargs):
        self.flow_events.append({"event": event_name, **kwargs})

    def _build_candidate_help_message(self) -> str:
        return "candidate help"

    def _build_employer_help_message(self) -> str:
        return "employer help"

    def _build_common_help_message(self) -> str:
        return "common help"


class PendingUploadRepoStub:
    def __init__(self) -> None:
        self.items = []
        self.set_calls: list[dict] = []

    async def list_non_terminal_for_user(self, **kwargs):
        return self.items

    async def set_status(self, **kwargs):
        self.set_calls.append(kwargs)


class RecoverySut(RecoveryHandlersMixin):
    def __init__(self) -> None:
        self._pending_upload_repo = PendingUploadRepoStub()
        self._conversation_state_service = DummyConversationStateService()
        self._telegram_client = DummyTelegramClient()

    def _build_pending_upload_recovery_message(
        self, *, role: str, recovered_kinds: list[str], state_reset: bool
    ) -> str:
        return f"recover:{role}:{len(recovered_kinds)}:{state_reset}"


class DedupStub:
    def __init__(self, *, start_ok: bool = True) -> None:
        self.start_ok = start_ok
        self.started: list[dict] = []
        self.processed: list[int] = []

    async def try_start_processing(self, **kwargs):
        self.started.append(kwargs)
        return self.start_ok

    async def mark_processed(self, *, update_id: int):
        self.processed.append(update_id)


class ActorRepoStub:
    def __init__(self) -> None:
        self.upserts: list[dict] = []

    async def upsert(self, **kwargs):
        self.upserts.append(kwargs)


class SessionStub:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def make_actor() -> TelegramUser:
    return TelegramUser.model_validate(
        {"id": 100, "is_bot": False, "first_name": "User", "username": "u"}
    )


def make_callback() -> TelegramCallbackQuery:
    return TelegramCallbackQuery.model_validate(
        {
            "id": "cb1",
            "from": {"id": 100, "is_bot": False, "first_name": "User", "username": "u"},
            "data": "x",
            "message": {"message_id": 10, "chat": {"id": 100, "type": "private"}},
        }
    )


def make_message_update(update_id: int = 1) -> TelegramUpdate:
    return TelegramUpdate.model_validate(
        {
            "update_id": update_id,
            "message": {
                "message_id": 11,
                "from": {"id": 100, "is_bot": False, "first_name": "User", "username": "u"},
                "chat": {"id": 100, "type": "private"},
                "text": "hi",
            },
        }
    )


@pytest.mark.asyncio
async def test_commands_select_role_cancel_and_help_paths() -> None:
    sut = CommandSut()
    callback = make_callback()
    actor = make_actor()

    bad = await sut._handle_select_role_callback(
        callback=callback,
        actor=actor,
        context=ResolvedCallbackContext(action_type="select_role", payload={"role": "bad"}),
    )
    assert bad["status"] == "ignored"

    selected = await sut._handle_select_role_callback(
        callback=callback,
        actor=actor,
        context=ResolvedCallbackContext(
            action_type="select_role", payload={"role": ROLE_CANDIDATE}
        ),
    )
    assert selected["action"] == "role_selected"
    assert sut.bootstrap_calls and sut._auth_session_service.login_calls

    message = make_message_update().message
    assert message is not None

    sut._conversation_state_service.state = SimpleNamespace(role_context=ROLE_EMPLOYER)
    cancel_dashboard = await sut._handle_cancel_command(message=message, actor=actor)
    assert cancel_dashboard["action"] == "cancel_to_dashboard"

    sut._conversation_state_service.state = None
    sut._auth_session_service.active_role = None
    cancel_none = await sut._handle_cancel_command(message=message, actor=actor)
    assert cancel_none["action"] == "cancel_no_active_role"

    sut._auth_session_service.active_role = ROLE_CANDIDATE
    help_candidate = await sut._handle_help_command(message=message, actor=actor)
    sut._auth_session_service.active_role = ROLE_EMPLOYER
    help_employer = await sut._handle_help_command(message=message, actor=actor)
    sut._auth_session_service.active_role = None
    help_common = await sut._handle_help_command(message=message, actor=actor)

    assert help_candidate["action"] == "help_candidate"
    assert help_employer["action"] == "help_employer"
    assert help_common["action"] == "help_common"


@dataclass
class UploadModel:
    target_kind: str


@pytest.mark.asyncio
async def test_recovery_handles_noop_and_recovery_cases() -> None:
    sut = RecoverySut()

    await sut._recover_pending_uploads_for_role(
        telegram_user_id=100,
        role=ROLE_CANDIDATE,
        chat_id=100,
    )
    assert sut._telegram_client.messages == []

    sut._pending_upload_repo.items = [
        UploadModel(target_kind="avatar"),
        UploadModel(target_kind="resume"),
    ]
    sut._conversation_state_service.state = SimpleNamespace(
        state_key=STATE_CANDIDATE_FILE_AWAIT_AVATAR
    )

    await sut._recover_pending_uploads_for_role(
        telegram_user_id=100,
        role=ROLE_CANDIDATE,
        chat_id=100,
    )

    assert len(sut._pending_upload_repo.set_calls) == 2
    assert sut._conversation_state_service.cleared == [100]
    assert len(sut._telegram_client.messages) == 1


@pytest.mark.asyncio
async def test_update_router_smoke_duplicate_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    processed_calls: list[tuple[str, str]] = []
    received_calls: list[str] = []

    import app.application.bot.services.update_router as update_router_module

    monkeypatch.setattr(
        update_router_module,
        "mark_update_processed",
        lambda update_type, status: processed_calls.append((update_type, status)),
    )
    monkeypatch.setattr(
        update_router_module,
        "mark_update_received",
        lambda update_type: received_calls.append(update_type),
    )

    # duplicate
    duplicate_sut = object.__new__(UpdateRouterService)
    duplicate_sut._dedup = DedupStub(start_ok=False)
    duplicate_sut._actor_repo = ActorRepoStub()
    duplicate_sut._session = SessionStub()
    duplicate_sut._log_flow_event = lambda *args, **kwargs: None

    duplicate = await duplicate_sut.route(make_message_update(1))
    assert duplicate["status"] == "duplicate"

    # success
    success_sut = object.__new__(UpdateRouterService)
    success_sut._dedup = DedupStub(start_ok=True)
    success_sut._actor_repo = ActorRepoStub()
    success_sut._session = SessionStub()
    success_sut._log_flow_event = lambda *args, **kwargs: None

    async def _handle_message(_message):
        return {"status": "processed", "action": "ok"}

    success_sut._handle_message = _handle_message
    success_sut._handle_callback = _handle_message

    result = await success_sut.route(make_message_update(2))
    assert result["status"] == "processed"
    assert success_sut._session.commits == 1
    assert success_sut._dedup.processed == [2]
    assert len(success_sut._actor_repo.upserts) == 1

    # failure
    fail_sut = object.__new__(UpdateRouterService)
    fail_sut._dedup = DedupStub(start_ok=True)
    fail_sut._actor_repo = ActorRepoStub()
    fail_sut._session = SessionStub()
    fail_sut._log_flow_event = lambda *args, **kwargs: None

    async def _boom(_message):
        raise RuntimeError("boom")

    fail_sut._handle_message = _boom
    fail_sut._handle_callback = _boom

    with pytest.raises(RuntimeError):
        await fail_sut.route(make_message_update(3))
    assert fail_sut._session.rollbacks == 1

    assert received_calls
    assert ("message", "duplicate") in processed_calls
    assert ("message", "processed") in processed_calls
    assert ("message", "failed") in processed_calls
