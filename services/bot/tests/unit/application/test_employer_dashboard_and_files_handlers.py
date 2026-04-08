from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.application.bot.constants import STATE_EMPLOYER_FILE_AWAIT_AVATAR
from app.application.bot.handlers.common.search_utils import SearchUtilsMixin
from app.application.bot.handlers.employer.dashboard import EmployerDashboardHandlersMixin
from app.application.bot.handlers.employer.files import EmployerFileHandlersMixin
from app.application.common.contracts import EmployerProfileSummary, SearchSessionSummary
from app.application.common.gateway_errors import EmployerGatewayError
from app.application.common.telegram_api import TelegramApiError
from app.application.employer.services.file_flow_service import EmployerFileFlowError
from app.schemas.telegram import TelegramCallbackQuery, TelegramMessage, TelegramUser


class DummyAuthService:
    def __init__(self, token: str | None = "token") -> None:
        self.token = token

    async def get_valid_access_token(self, *, telegram_user_id: int) -> str | None:
        return self.token


class DummyTelegramClient:
    def __init__(self) -> None:
        self.answered: list[dict] = []
        self.messages: list[dict] = []
        self.attachment_messages: list[dict] = []
        self.photos: list[dict] = []
        self.docs: list[dict] = []
        self.raise_photo = False
        self.raise_doc = False

    async def answer_callback_query(self, **kwargs):
        self.answered.append(kwargs)

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)

    async def send_attachment_message(self, **kwargs):
        self.attachment_messages.append(kwargs)

    async def send_photo(self, **kwargs):
        if self.raise_photo:
            raise TelegramApiError("photo failed")
        self.photos.append(kwargs)

    async def send_document(self, **kwargs):
        if self.raise_doc:
            raise TelegramApiError("doc failed")
        self.docs.append(kwargs)


class DummyEmployerGateway:
    def __init__(self) -> None:
        self.raise_error = False
        self.employer: EmployerProfileSummary | None = EmployerProfileSummary(
            id=uuid4(),
            telegram_id=100,
            company="Acme",
            avatar_file_id=None,
            avatar_download_url="https://example.com/a.jpg",
            document_file_id=None,
            document_download_url="https://example.com/d.pdf",
            contacts={},
        )
        self.searches: list[SearchSessionSummary] = []

    async def get_by_telegram(self, *, access_token: str, telegram_id: int):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return self.employer

    async def list_searches(self, *, access_token: str, employer_id, limit: int):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return self.searches

    async def delete_avatar(self, *, access_token: str, employer_id, idempotency_key: str):
        if self.raise_error:
            raise EmployerGatewayError("boom")

    async def delete_document(self, *, access_token: str, employer_id, idempotency_key: str):
        if self.raise_error:
            raise EmployerGatewayError("boom")


@dataclass
class DummyState:
    state_key: str


class DummyConversationStateService:
    def __init__(self) -> None:
        self.cleared: list[int] = []

    async def clear_state(self, *, telegram_user_id: int) -> None:
        self.cleared.append(telegram_user_id)


class DummyEmployerFileFlowService:
    def __init__(self) -> None:
        self.raise_validation = False
        self.raise_gateway = False
        self.raise_generic = False

    async def process_avatar_upload(self, **kwargs):
        if self.raise_validation:
            raise EmployerFileFlowError("bad avatar")
        if self.raise_gateway:
            raise EmployerGatewayError("gateway")
        if self.raise_generic:
            raise RuntimeError("boom")

    async def process_document_upload(self, **kwargs):
        if self.raise_validation:
            raise EmployerFileFlowError("bad doc")
        if self.raise_gateway:
            raise EmployerGatewayError("gateway")
        if self.raise_generic:
            raise RuntimeError("boom")


class DummyEmployerDashboard(EmployerDashboardHandlersMixin, SearchUtilsMixin):
    def __init__(self) -> None:
        self._auth_session_service = DummyAuthService()
        self._telegram_client = DummyTelegramClient()
        self._employer_gateway = DummyEmployerGateway()
        self._conversation_state_service = DummyConversationStateService()
        self.calls: list[tuple[str, dict]] = []

    async def _run_employer_gateway_call(
        self, *, telegram_user_id: int, access_token: str, operation
    ):
        return await operation(access_token)

    async def _expired_session_callback(self, callback):
        self.calls.append(("expired", {"callback": callback}))

    async def _answer_callback_and_handle_gateway_error(self, **kwargs):
        self.calls.append(("gateway_error", kwargs))

    async def _send_retry_action_if_temporarily_unavailable(self, **kwargs):
        self.calls.append(("retry", kwargs))

    def _resolve_chat_id(self, callback, actor) -> int:
        return actor.id

    async def _render_callback_screen(self, **kwargs):
        self.calls.append(("render", kwargs))

    async def _render_callback_screen_with_optional_photo(self, **kwargs):
        self.calls.append(("render_photo", kwargs))

    async def _set_state_and_render_wizard_step(self, **kwargs):
        self.calls.append(("wizard", kwargs))

    def _build_employer_dashboard_message(self, **kwargs) -> str:
        return "dashboard"

    async def _build_employer_dashboard_markup(self, telegram_user_id: int):
        return {"dashboard": telegram_user_id}

    async def _build_employer_search_wizard_controls_markup(self, **kwargs):
        return {"controls": kwargs}

    async def _build_employer_edit_section_markup(self, **kwargs):
        return {"edit": kwargs}

    async def _build_employer_files_section_markup(self, **kwargs):
        return {"files": kwargs}

    async def _build_employer_search_section_markup(self, **kwargs):
        return {"search_section": kwargs}

    async def _build_open_search_markup(self, **kwargs):
        return {"open": kwargs}

    def _build_employer_profile_message(self, **kwargs) -> str:
        return "profile"

    async def _build_employer_profile_view_markup(self, **kwargs):
        return {"profile": True}

    def _build_employer_help_message(self) -> str:
        return "help"

    async def _build_employer_back_to_dashboard_markup(self, **kwargs):
        return {"back": kwargs}

    async def _safe_get_employer_statistics(self, **kwargs):
        return {"total": 1}

    def _build_employer_stats_message(self, employer, stats) -> str:
        return "stats"

    def _humanize_search_status(self, value: str | None) -> str:
        return value or "—"


class DummyEmployerFiles(EmployerFileHandlersMixin, SearchUtilsMixin):
    def __init__(self) -> None:
        self._auth_session_service = DummyAuthService()
        self._telegram_client = DummyTelegramClient()
        self._employer_gateway = DummyEmployerGateway()
        self._employer_file_flow_service = DummyEmployerFileFlowService()
        self._conversation_state_service = DummyConversationStateService()
        self.calls: list[tuple[str, dict]] = []

    async def _run_employer_gateway_call(
        self, *, telegram_user_id: int, access_token: str, operation
    ):
        return await operation(access_token)

    async def _expired_session_callback(self, callback):
        self.calls.append(("expired", {"callback": callback}))

    async def _answer_callback_and_handle_gateway_error(self, **kwargs):
        self.calls.append(("gateway_error", kwargs))

    async def _handle_employer_gateway_error(self, **kwargs):
        self.calls.append(("handle_gateway_error", kwargs))

    async def _safe_get_employer_statistics(self, **kwargs):
        return {"total": 1}

    async def _build_employer_dashboard_markup(self, telegram_user_id: int):
        return {"dashboard": telegram_user_id}

    def _build_employer_dashboard_message(self, **kwargs) -> str:
        return "dashboard"

    async def _render_callback_screen(self, **kwargs):
        self.calls.append(("render", kwargs))

    def _resolve_chat_id(self, callback, actor) -> int:
        return actor.id


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


def make_actor() -> TelegramUser:
    return TelegramUser.model_validate({"id": 100, "is_bot": False, "first_name": "User"})


def make_message() -> TelegramMessage:
    return TelegramMessage.model_validate(
        {
            "message_id": 1,
            "from": {"id": 100, "is_bot": False, "first_name": "User"},
            "chat": {"id": 100, "type": "private"},
            "text": "text",
        }
    )


@pytest.mark.asyncio
async def test_employer_dashboard_and_profile_branches() -> None:
    sut = DummyEmployerDashboard()
    callback = make_callback()
    actor = make_actor()

    sut._auth_session_service.token = None
    expired = await sut._handle_employer_dashboard(callback=callback, actor=actor)
    assert expired["action"] == "session_expired"

    sut._auth_session_service.token = "token"
    sut._employer_gateway.raise_error = True
    err = await sut._handle_employer_dashboard(callback=callback, actor=actor)
    assert err["action"] == "employer_gateway_error"

    sut._employer_gateway.raise_error = False
    sut._employer_gateway.employer = None
    not_found = await sut._handle_employer_profile(callback=callback, actor=actor)
    assert not_found["action"] == "employer_not_found"

    sut._employer_gateway.employer = EmployerProfileSummary(
        id=uuid4(),
        telegram_id=100,
        company="Acme",
        avatar_file_id=None,
        avatar_download_url=None,
        document_file_id=None,
        document_download_url=None,
        contacts={},
    )
    ok_dashboard = await sut._handle_employer_dashboard(callback=callback, actor=actor)
    ok_profile = await sut._handle_employer_profile(callback=callback, actor=actor)
    assert ok_dashboard["action"] == "employer_dashboard"
    assert ok_profile["action"] == "employer_profile"


@pytest.mark.asyncio
async def test_employer_dashboard_sections_and_help_stats() -> None:
    sut = DummyEmployerDashboard()
    callback = make_callback()
    actor = make_actor()

    sut._employer_gateway.searches = []
    search_section = await sut._handle_employer_open_search_section(callback=callback, actor=actor)
    assert search_section["action"] == "employer_menu_open_search_section"

    continue_empty = await sut._handle_employer_continue_active_search(
        callback=callback, actor=actor
    )
    assert continue_empty["action"] == "employer_continue_active_search_empty"

    sut._employer_gateway.searches = [
        SearchSessionSummary(
            id=uuid4(),
            employer_id=sut._employer_gateway.employer.id,
            title="S",
            status="active",
            role="python",
        )
    ]
    continue_ok = await sut._handle_employer_continue_active_search(callback=callback, actor=actor)
    assert continue_ok["action"] == "employer_continue_active_search"

    open_files = await sut._handle_employer_open_files_section(callback=callback, actor=actor)
    assert open_files["action"] == "employer_menu_open_files_section"

    open_edit = await sut._handle_employer_open_edit_section(callback=callback, actor=actor)
    cancel_edit = await sut._handle_employer_edit_cancel(callback=callback, actor=actor)
    start_wizard = await sut._handle_employer_start_search_wizard(callback=callback, actor=actor)
    help_result = await sut._handle_employer_help(callback=callback, actor=actor)
    stats_result = await sut._handle_employer_stats(callback=callback, actor=actor)

    assert open_edit["action"] == "employer_menu_open_edit_section"
    assert cancel_edit["action"] == "employer_edit_cancel"
    assert sut._conversation_state_service.cleared[-1] == actor.id
    assert start_wizard["action"] == "employer_search_create_started"
    assert help_result["action"] == "employer_help"
    assert stats_result["action"] == "employer_stats"


@pytest.mark.asyncio
async def test_employer_file_upload_state_branches() -> None:
    sut = DummyEmployerFiles()
    actor = make_actor()
    msg = make_message()

    sut._auth_session_service.token = None
    expired = await sut._handle_employer_file_upload_state(
        message=msg,
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_FILE_AWAIT_AVATAR),
        chat_id=100,
    )
    assert expired["action"] == "session_expired"

    sut._auth_session_service.token = "token"
    sut._employer_gateway.raise_error = True
    gw_err = await sut._handle_employer_file_upload_state(
        message=msg,
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_FILE_AWAIT_AVATAR),
        chat_id=100,
    )
    assert gw_err["action"] == "employer_gateway_error"

    sut._employer_gateway.raise_error = False
    sut._employer_gateway.employer = None
    not_found = await sut._handle_employer_file_upload_state(
        message=msg,
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_FILE_AWAIT_AVATAR),
        chat_id=100,
    )
    assert not_found["action"] == "employer_not_found"

    sut._employer_gateway.employer = EmployerProfileSummary(
        id=uuid4(),
        telegram_id=100,
        company="Acme",
        avatar_file_id=None,
        avatar_download_url=None,
        document_file_id=None,
        document_download_url=None,
        contacts={},
    )
    sut._employer_file_flow_service.raise_validation = True
    validation = await sut._handle_employer_file_upload_state(
        message=msg,
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_FILE_AWAIT_AVATAR),
        chat_id=100,
    )
    assert validation["action"] == "employer_file_upload_validation_failed"

    sut._employer_file_flow_service.raise_validation = False
    sut._employer_file_flow_service.raise_generic = True
    failed = await sut._handle_employer_file_upload_state(
        message=msg,
        actor=actor,
        state=DummyState(state_key=STATE_EMPLOYER_FILE_AWAIT_AVATAR),
        chat_id=100,
    )
    assert failed["action"] == "employer_file_upload_failed"


@pytest.mark.asyncio
async def test_employer_download_and_delete_file_branches() -> None:
    sut = DummyEmployerFiles()
    callback = make_callback()
    actor = make_actor()

    sut._auth_session_service.token = None
    expired = await sut._handle_employer_download_file(
        callback=callback, actor=actor, target_kind="avatar"
    )
    assert expired["action"] == "session_expired"

    sut._auth_session_service.token = "token"
    sut._employer_gateway.raise_error = True
    gw_err = await sut._handle_employer_download_file(
        callback=callback, actor=actor, target_kind="avatar"
    )
    assert gw_err["action"] == "employer_gateway_error"

    sut._employer_gateway.raise_error = False
    sut._employer_gateway.employer = None
    not_found = await sut._handle_employer_download_file(
        callback=callback, actor=actor, target_kind="avatar"
    )
    assert not_found["action"] == "employer_not_found"

    sut._employer_gateway.employer = EmployerProfileSummary(
        id=uuid4(),
        telegram_id=100,
        company="Acme",
        avatar_file_id=None,
        avatar_download_url=None,
        document_file_id=None,
        document_download_url="https://example.com/doc.pdf",
        contacts={},
    )
    missing = await sut._handle_employer_download_file(
        callback=callback, actor=actor, target_kind="avatar"
    )
    assert missing["action"] == "employer_download_file_missing"

    sut._employer_gateway.employer = EmployerProfileSummary(
        id=uuid4(),
        telegram_id=100,
        company="Acme",
        avatar_file_id=None,
        avatar_download_url="https://example.com/a.jpg",
        document_file_id=None,
        document_download_url="https://example.com/doc.pdf",
        contacts={},
    )
    avatar_ok = await sut._handle_employer_download_file(
        callback=callback, actor=actor, target_kind="avatar"
    )
    assert avatar_ok["action"] == "employer_avatar_downloaded"

    sut._telegram_client.raise_doc = True
    doc_link = await sut._handle_employer_download_file(
        callback=callback, actor=actor, target_kind="document"
    )
    assert doc_link["action"] == "employer_document_download_link_sent"
    assert sut._telegram_client.attachment_messages == [
        {
            "chat_id": 100,
            "text": "Ссылка на файл:\nhttps://example.com/doc.pdf",
        }
    ]
    assert sut._telegram_client.messages == []

    delete_avatar = await sut._handle_employer_delete_file(
        callback=callback, actor=actor, target_kind="avatar"
    )
    assert delete_avatar["action"] == "employer_avatar_deleted"

    delete_doc = await sut._handle_employer_delete_file(
        callback=callback, actor=actor, target_kind="document"
    )
    assert delete_doc["action"] == "employer_document_deleted"
    render_calls = [payload for name, payload in sut.calls if name == "render"]
    assert len(render_calls) == 2
    assert "Аватар компании удалён." in render_calls[0]["text"]
    assert "Документ компании удалён." in render_calls[1]["text"]
