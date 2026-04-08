from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.bot.constants import (
    STATE_EMPLOYER_SEARCH_ABOUT,
    STATE_EMPLOYER_SEARCH_CONFIRM,
    STATE_EMPLOYER_SEARCH_ENGLISH,
    STATE_EMPLOYER_SEARCH_LOCATION,
    STATE_EMPLOYER_SEARCH_MUST_SKILLS,
    STATE_EMPLOYER_SEARCH_TITLE,
    STATE_EMPLOYER_SEARCH_WORK_MODES,
)
from app.application.bot.handlers.common.utils import CommonUtilsMixin
from app.application.bot.handlers.common.search_utils import SearchUtilsMixin
from app.application.bot.handlers.employer.search import EmployerSearchHandlersMixin
from app.application.bot.ui.profile_message_mixins.shared import ProfileSharedMessagesMixin
from app.application.common.contracts import (
    CandidateProfileSummary,
    ContactAccessResultView,
    EmployerProfileSummary,
    NextCandidateResultView,
    SearchSessionSummary,
)
from app.application.common.gateway_errors import EmployerGatewayError
from app.application.common.telegram_api import TelegramApiError
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser


@dataclass
class DummyState:
    state_key: str
    payload: dict | None = None


class DummyConversationStateService:
    def __init__(self) -> None:
        self.state: DummyState | None = None
        self.cleared: list[int] = []

    async def get_state(self, *, telegram_user_id: int):
        return self.state

    async def clear_state(self, *, telegram_user_id: int):
        self.cleared.append(telegram_user_id)
        self.state = None


class DummyAuthSessionService:
    def __init__(self, token: str | None = "token") -> None:
        self.token = token

    async def get_valid_access_token(self, *, telegram_user_id: int) -> str | None:
        return self.token


class DummyTelegramClient:
    def __init__(self) -> None:
        self.answered: list[dict] = []
        self.sent_messages: list[dict] = []
        self.attachment_messages: list[dict] = []
        self.sent_docs: list[dict] = []
        self.raise_on_send_document = False

    async def answer_callback_query(self, **kwargs):
        self.answered.append(kwargs)

    async def send_message(self, **kwargs):
        self.sent_messages.append(kwargs)

    async def send_attachment_message(self, **kwargs):
        self.attachment_messages.append(kwargs)

    async def send_document(self, **kwargs):
        if self.raise_on_send_document:
            raise TelegramApiError("send failed")
        self.sent_docs.append(kwargs)


class DummyEmployerGateway:
    def __init__(self) -> None:
        self.employer = EmployerProfileSummary(
            id=uuid4(),
            telegram_id=100,
            company="Acme",
            avatar_file_id=None,
            avatar_download_url=None,
            document_file_id=None,
            document_download_url=None,
            contacts={},
        )
        self.search = SearchSessionSummary(
            id=uuid4(),
            employer_id=self.employer.id,
            title="Search",
            status="active",
            role="python",
        )
        self.next_result = NextCandidateResultView(
            candidate=CandidateProfileSummary(
                id=uuid4(),
                telegram_id=101,
                display_name="John",
                headline_role="Python",
                location="Moscow",
                status="active",
                avatar_file_id=None,
                avatar_download_url=None,
                resume_file_id=None,
                resume_download_url=None,
                version_id=1,
            ),
            message=None,
            is_degraded=False,
        )
        self.contact_result = ContactAccessResultView(granted=False, status="pending")
        self.searches: list[SearchSessionSummary] = [self.search]
        self.favorites: list[CandidateProfileSummary] = []
        self.unlocked: list[CandidateProfileSummary] = []
        self.raise_error = False

    async def get_by_telegram(self, *, access_token: str, telegram_id: int):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return self.employer

    async def pause_search_session(self, *, access_token: str, session_id, idempotency_key: str):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return SearchSessionSummary(
            id=session_id,
            employer_id=self.employer.id,
            title="Search",
            status="paused",
            role="python",
        )

    async def resume_search_session(self, *, access_token: str, session_id, idempotency_key: str):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return SearchSessionSummary(
            id=session_id,
            employer_id=self.employer.id,
            title="Search",
            status="active",
            role="python",
        )

    async def close_search_session(self, *, access_token: str, session_id, idempotency_key: str):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return SearchSessionSummary(
            id=session_id,
            employer_id=self.employer.id,
            title="Search",
            status="closed",
            role="python",
        )

    async def get_next_candidate(self, *, access_token: str, session_id):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return self.next_result

    async def request_contact_access(
        self, *, access_token: str, employer_id, candidate_id, idempotency_key: str
    ):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return self.contact_result

    async def list_searches(self, *, access_token: str, employer_id, limit: int):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return self.searches

    async def get_favorites(self, *, access_token: str, employer_id):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return self.favorites

    async def get_unlocked_contacts(self, *, access_token: str, employer_id):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return self.unlocked

    async def create_search_session(
        self,
        *,
        access_token: str,
        employer_id,
        title: str,
        filters: dict,
        idempotency_key: str,
    ):
        if self.raise_error:
            raise EmployerGatewayError("boom")
        return SearchSessionSummary(
            id=uuid4(),
            employer_id=employer_id,
            title=title,
            status="active",
            role=str(filters.get("role", "")),
        )


class DummyEmployerSearch(
    EmployerSearchHandlersMixin, SearchUtilsMixin, CommonUtilsMixin, ProfileSharedMessagesMixin
):
    def __init__(self) -> None:
        self._conversation_state_service = DummyConversationStateService()
        self._auth_session_service = DummyAuthSessionService()
        self._telegram_client = DummyTelegramClient()
        self._employer_gateway = DummyEmployerGateway()
        self.calls: list[tuple[str, dict]] = []

    async def _run_employer_gateway_call(
        self, *, telegram_user_id: int, access_token: str, operation
    ):
        return await operation(access_token)

    def _resolve_chat_id(self, callback: TelegramCallbackQuery, actor: TelegramUser) -> int:
        return actor.id

    async def _expired_session_callback(self, callback):
        self.calls.append(("expired", {"callback": callback}))

    async def _answer_callback_and_handle_gateway_error(self, **kwargs):
        self.calls.append(("gateway_error", kwargs))

    async def _send_retry_action_if_temporarily_unavailable(self, **kwargs):
        self.calls.append(("retry", kwargs))

    async def _render_callback_screen(self, **kwargs):
        self.calls.append(("render", kwargs))

    async def _set_state_and_render_wizard_step(self, **kwargs):
        self.calls.append(("wizard", kwargs))

    async def _render_employer_search_confirm_step(self, **kwargs):
        self.calls.append(("confirm", kwargs))

    async def _render_employer_search_work_modes_step(self, **kwargs):
        self.calls.append(("work_modes_step", kwargs))

    async def _render_employer_search_english_step(self, **kwargs):
        self.calls.append(("english_step", kwargs))

    async def _build_next_candidate_only_markup(self, **kwargs):
        return {"next": kwargs}

    async def _build_no_candidate_markup(self, **kwargs):
        return {"none": kwargs}

    async def _build_candidate_decision_markup(self, **kwargs):
        return {"decision": kwargs}

    async def _build_candidate_collection_profile_markup(self, **kwargs):
        return {"profile": kwargs}

    async def _build_employer_dashboard_markup(self, telegram_user_id: int):
        return {"dashboard": telegram_user_id}

    async def _build_employer_search_wizard_controls_markup(self, **kwargs):
        return {"controls": kwargs}

    async def _build_employer_search_work_modes_selector_markup(self, **kwargs):
        return {"wm": kwargs}

    async def _build_employer_search_english_selector_markup(self, **kwargs):
        return {"eng": kwargs}

    async def _build_open_search_markup(self, **kwargs):
        return {"open": kwargs}

    def _build_search_session_status_message(self, search: SearchSessionSummary) -> str:
        return f"status:{search.status}"

    def _build_next_candidate_message(self, result: NextCandidateResultView) -> str:
        return "candidate" if result.candidate else "none"

    def _build_contact_access_result_message(self, result: ContactAccessResultView) -> str:
        return f"contact:{result.status}"

    def _extract_payload_text(self, payload: dict | None, key: str) -> str | None:
        if not isinstance(payload, dict):
            return None
        raw = payload.get(key)
        if raw is None:
            return None
        normalized = str(raw).strip()
        return normalized or None

    def _extract_page_number(self, payload: dict | None) -> int:
        if not payload:
            return 1
        return int(payload.get("page", 1))

    def _paginate_items(self, items: list, page: int):
        return items, max(1, page), 1

    def _build_searches_list_message(
        self, searches: list[SearchSessionSummary], *, page: int, total_pages: int
    ) -> str:
        return f"searches:{len(searches)}:{page}/{total_pages}"

    async def _build_searches_list_markup(self, *args, **kwargs):
        return {"searches": True}

    async def _build_employer_searches_empty_markup(self, **kwargs):
        return {"empty": True}

    def _build_candidate_collection_message(
        self, *, title: str, items: list[CandidateProfileSummary]
    ) -> str:
        return f"{title}:{len(items)}"

    async def _build_candidate_collection_markup(self, **kwargs):
        return {"collection": kwargs}


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


def ctx(**payload):
    return SimpleNamespace(payload=payload)


@pytest.mark.asyncio
async def test_search_control_guard_and_noop_branches() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()
    session_id = str(uuid4())

    unknown = await sut._handle_employer_search_control(
        callback=callback,
        actor=actor,
        context=ctx(session_id=session_id, search_status="active"),
        operation="bad",
    )
    assert unknown["reason"] == "unknown_search_control_operation"

    pause_noop = await sut._handle_employer_search_control(
        callback=callback,
        actor=actor,
        context=ctx(session_id=session_id, search_status="paused"),
        operation="pause",
    )
    assert pause_noop["action"] == "employer_search_pause_noop"

    resume_noop = await sut._handle_employer_search_control(
        callback=callback,
        actor=actor,
        context=ctx(session_id=session_id, search_status="active"),
        operation="resume",
    )
    assert resume_noop["action"] == "employer_search_resume_noop"

    close_noop = await sut._handle_employer_search_control(
        callback=callback,
        actor=actor,
        context=ctx(session_id=session_id, search_status="closed"),
        operation="close",
    )
    assert close_noop["action"] == "employer_search_close_noop"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation, search_status, expected",
    [
        ("pause", "active", "employer_search_pause"),
        ("resume", "paused", "employer_search_resume"),
        ("close", "active", "employer_search_close"),
    ],
)
async def test_search_control_success(
    operation: str,
    search_status: str,
    expected: str,
) -> None:
    sut = DummyEmployerSearch()
    result = await sut._handle_employer_search_control(
        callback=make_callback(),
        actor=make_actor(),
        context=ctx(session_id=str(uuid4()), search_status=search_status),
        operation=operation,
    )
    assert result["action"] == expected
    assert any(name == "render" for name, _ in sut.calls)


@pytest.mark.asyncio
async def test_search_control_gateway_error() -> None:
    sut = DummyEmployerSearch()
    sut._employer_gateway.raise_error = True
    result = await sut._handle_employer_search_control(
        callback=make_callback(),
        actor=make_actor(),
        context=ctx(session_id=str(uuid4()), search_status="active"),
        operation="pause",
    )
    assert result["action"] == "employer_gateway_error"


@pytest.mark.asyncio
async def test_work_mode_choice_toggle_and_done() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()

    expired = await sut._handle_employer_search_choice_work_mode_toggle(
        callback=callback,
        actor=actor,
        context=ctx(mode="remote"),
    )
    assert expired["action"] == "employer_search_work_modes_choice_expired"

    sut._conversation_state_service.state = DummyState(
        state_key=STATE_EMPLOYER_SEARCH_WORK_MODES,
        payload={"work_modes": ["remote"]},
    )
    invalid = await sut._handle_employer_search_choice_work_mode_toggle(
        callback=callback,
        actor=actor,
        context=ctx(mode="mars"),
    )
    assert invalid["action"] == "employer_search_work_modes_choice_invalid"

    toggled = await sut._handle_employer_search_choice_work_mode_toggle(
        callback=callback,
        actor=actor,
        context=ctx(mode="onsite"),
    )
    assert toggled["action"] == "employer_search_work_modes_choice_toggled"

    done = await sut._handle_employer_search_choice_work_modes_done(
        callback=callback,
        actor=actor,
    )
    assert done["action"] == "employer_search_work_modes_saved"


@pytest.mark.asyncio
async def test_english_choice_branches() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()

    expired = await sut._handle_employer_search_choice_english(
        callback=callback,
        actor=actor,
        context=ctx(value="B2"),
    )
    assert expired["action"] == "employer_search_english_choice_expired"

    sut._conversation_state_service.state = DummyState(
        state_key=STATE_EMPLOYER_SEARCH_ENGLISH, payload={}
    )

    invalid = await sut._handle_employer_search_choice_english(
        callback=callback,
        actor=actor,
        context=ctx(value="ZZ"),
    )
    assert invalid["action"] == "employer_search_english_choice_invalid"

    saved = await sut._handle_employer_search_choice_english(
        callback=callback,
        actor=actor,
        context=ctx(value="B2"),
    )
    assert saved["action"] == "employer_search_english_saved"


@pytest.mark.asyncio
async def test_wizard_control_branches() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()

    expired = await sut._handle_employer_search_wizard_control(
        callback=callback,
        actor=actor,
        context=ctx(step="role"),
        control="skip",
    )
    assert expired["action"] == "employer_search_wizard_step_expired"

    sut._conversation_state_service.state = DummyState(
        state_key=STATE_EMPLOYER_SEARCH_TITLE, payload={}
    )
    skip_not_allowed = await sut._handle_employer_search_wizard_control(
        callback=callback,
        actor=actor,
        context=ctx(step="title"),
        control="skip",
    )
    assert skip_not_allowed["action"] == "employer_search_wizard_skip_not_allowed"

    back_not_allowed = await sut._handle_employer_search_wizard_control(
        callback=callback,
        actor=actor,
        context=ctx(step="title"),
        control="back",
    )
    assert back_not_allowed["action"] == "employer_search_wizard_back_not_allowed"

    sut._conversation_state_service.state = DummyState(
        state_key=STATE_EMPLOYER_SEARCH_LOCATION, payload={"_employer_search_edit_step": "location"}
    )
    back_to_confirm = await sut._handle_employer_search_wizard_control(
        callback=callback,
        actor=actor,
        context=ctx(step="location"),
        control="back",
    )
    assert back_to_confirm["action"] == "employer_search_wizard_back_to_confirm"

    cancel = await sut._handle_employer_search_wizard_control(
        callback=callback,
        actor=actor,
        context=ctx(step="location"),
        control="cancel",
    )
    assert cancel["action"] == "employer_search_wizard_cancelled"


@pytest.mark.asyncio
async def test_wizard_skip_paths() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()

    sut._conversation_state_service.state = DummyState(
        state_key=STATE_EMPLOYER_SEARCH_MUST_SKILLS, payload={}
    )
    skipped = await sut._handle_employer_search_wizard_control(
        callback=callback,
        actor=actor,
        context=ctx(step="must_skills"),
        control="skip",
    )
    assert skipped["action"] == "employer_search_wizard_skipped_must_skills"

    sut._conversation_state_service.state = DummyState(
        state_key=STATE_EMPLOYER_SEARCH_ABOUT, payload={}
    )
    skipped_about = await sut._handle_employer_search_wizard_control(
        callback=callback,
        actor=actor,
        context=ctx(step="about"),
        control="skip",
    )
    assert skipped_about["action"] == "employer_search_wizard_skipped_about"


@pytest.mark.asyncio
async def test_open_search_branches() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()
    session_id = str(uuid4())

    closed = await sut._handle_employer_open_search(
        callback=callback,
        actor=actor,
        context=ctx(session_id=session_id, search_status="closed"),
    )
    assert closed["action"] == "employer_open_search_closed"

    paused = await sut._handle_employer_open_search(
        callback=callback,
        actor=actor,
        context=ctx(session_id=session_id, search_status="paused"),
    )
    assert paused["action"] == "employer_open_search_paused"

    sut._employer_gateway.raise_error = True
    err = await sut._handle_employer_open_search(
        callback=callback,
        actor=actor,
        context=ctx(session_id=session_id, search_status="active"),
    )
    assert err["action"] == "employer_gateway_error"

    sut._employer_gateway.raise_error = False
    ok = await sut._handle_employer_open_search(
        callback=callback,
        actor=actor,
        context=ctx(session_id=session_id, search_status="active"),
    )
    assert ok["action"] == "employer_open_search"


@pytest.mark.asyncio
async def test_resume_download_branches() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()

    missing = await sut._handle_employer_search_resume_download(
        callback=callback,
        actor=actor,
        context=ctx(resume_download_url=""),
    )
    assert missing["action"] == "employer_search_resume_missing"

    sent = await sut._handle_employer_search_resume_download(
        callback=callback,
        actor=actor,
        context=ctx(resume_download_url="https://example.com/r.pdf"),
    )
    assert sent["action"] == "employer_search_resume_sent"

    sut._telegram_client.raise_on_send_document = True
    sent_link = await sut._handle_employer_search_resume_download(
        callback=callback,
        actor=actor,
        context=ctx(resume_download_url="https://example.com/r.pdf"),
    )
    assert sent_link["action"] == "employer_search_resume_link_sent"
    assert sut._telegram_client.attachment_messages == [
        {
            "chat_id": 100,
            "text": "Ссылка на резюме:\nhttps://example.com/r.pdf",
        }
    ]
    assert sut._telegram_client.sent_messages == []


@pytest.mark.asyncio
async def test_request_contact_access_branches() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()
    session_id = str(uuid4())
    candidate_id = str(uuid4())

    requires_like = await sut._handle_employer_request_contact_access(
        callback=callback,
        actor=actor,
        context=ctx(
            session_id=session_id, candidate_id=candidate_id, search_status="active", liked=False
        ),
    )
    assert requires_like["action"] == "employer_request_contact_requires_like"

    sut._auth_session_service.token = None
    expired = await sut._handle_employer_request_contact_access(
        callback=callback,
        actor=actor,
        context=ctx(
            session_id=session_id, candidate_id=candidate_id, search_status="active", liked=True
        ),
    )
    assert expired["action"] == "session_expired"

    sut._auth_session_service.token = "token"
    sut._employer_gateway.raise_error = True
    err = await sut._handle_employer_request_contact_access(
        callback=callback,
        actor=actor,
        context=ctx(
            session_id=session_id, candidate_id=candidate_id, search_status="active", liked=True
        ),
    )
    assert err["action"] == "employer_gateway_error"

    sut._employer_gateway.raise_error = False
    ok = await sut._handle_employer_request_contact_access(
        callback=callback,
        actor=actor,
        context=ctx(
            session_id=session_id, candidate_id=candidate_id, search_status="active", liked=True
        ),
    )
    assert ok["action"] == "employer_request_contact_access"


@pytest.mark.asyncio
async def test_list_searches_branches() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()

    sut._auth_session_service.token = None
    expired = await sut._handle_employer_list_searches(
        callback=callback, actor=actor, context=ctx(page=2)
    )
    assert expired["action"] == "session_expired"

    sut._auth_session_service.token = "token"
    sut._employer_gateway.employer = None
    not_found = await sut._handle_employer_list_searches(
        callback=callback, actor=actor, context=ctx(page=1)
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
    sut._employer_gateway.raise_error = True
    err = await sut._handle_employer_list_searches(
        callback=callback, actor=actor, context=ctx(page=1)
    )
    assert err["action"] == "employer_gateway_error"

    sut._employer_gateway.raise_error = False
    sut._employer_gateway.searches = []
    empty = await sut._handle_employer_list_searches(
        callback=callback, actor=actor, context=ctx(page=1)
    )
    assert empty["action"] == "employer_list_searches_empty"

    sut._employer_gateway.searches = [
        SearchSessionSummary(
            id=uuid4(),
            employer_id=sut._employer_gateway.employer.id,
            title="S",
            status="active",
            role="python",
        )
    ]
    ok = await sut._handle_employer_list_searches(
        callback=callback, actor=actor, context=ctx(page=1)
    )
    assert ok["action"] == "employer_list_searches"


@pytest.mark.asyncio
async def test_favorites_and_unlocked_branches() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()
    candidate = CandidateProfileSummary(
        id=uuid4(),
        telegram_id=102,
        display_name="Jane",
        headline_role="Go",
        location="SPB",
        status="active",
        avatar_file_id=None,
        avatar_download_url=None,
        resume_file_id=None,
        resume_download_url=None,
        version_id=1,
    )

    sut._employer_gateway.favorites = [candidate]
    favorites = await sut._handle_employer_favorites(
        callback=callback, actor=actor, context=ctx(page=1)
    )
    assert favorites["action"] == "employer_favorites"

    sut._employer_gateway.unlocked = [candidate]
    unlocked = await sut._handle_employer_unlocked_contacts(
        callback=callback, actor=actor, context=ctx(page=1)
    )
    assert unlocked["action"] == "employer_unlocked_contacts"


@pytest.mark.asyncio
async def test_open_collection_candidate_branches() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()
    candidate = CandidateProfileSummary(
        id=uuid4(),
        telegram_id=102,
        display_name="Jane",
        headline_role="Go",
        location="SPB",
        status="active",
        avatar_file_id=None,
        avatar_download_url=None,
        resume_file_id=None,
        resume_download_url=None,
        version_id=1,
    )
    sut._employer_gateway.favorites = [candidate]

    invalid_id = await sut._handle_employer_open_collection_candidate(
        callback=callback,
        actor=actor,
        context=ctx(source="favorites", candidate_id="bad"),
    )
    assert invalid_id["action"] == "employer_collection_candidate_invalid_id"

    invalid_source = await sut._handle_employer_open_collection_candidate(
        callback=callback,
        actor=actor,
        context=ctx(source="bad", candidate_id=str(candidate.id)),
    )
    assert invalid_source["action"] == "employer_collection_candidate_invalid_source"

    not_found = await sut._handle_employer_open_collection_candidate(
        callback=callback,
        actor=actor,
        context=ctx(source="favorites", candidate_id=str(uuid4())),
    )
    assert not_found["action"] == "employer_collection_candidate_not_found"

    opened = await sut._handle_employer_open_collection_candidate(
        callback=callback,
        actor=actor,
        context=ctx(source="favorites", candidate_id=str(candidate.id), page=2, total_pages=4),
    )
    assert opened["action"] == "employer_collection_candidate_opened"
    render_call = next(call for call in sut.calls if call[0] == "render")
    assert render_call[1]["reply_markup"]["profile"]["source"] == "favorites"
    assert render_call[1]["reply_markup"]["profile"]["page"] == 2


@pytest.mark.asyncio
async def test_search_create_confirm_branches() -> None:
    sut = DummyEmployerSearch()
    callback = make_callback()
    actor = make_actor()

    expired = await sut._handle_employer_search_create_confirm(
        callback=callback,
        actor=actor,
        context=ctx(confirm=True),
    )
    assert expired["action"] == "employer_search_confirm_expired"

    sut._conversation_state_service.state = DummyState(
        state_key=STATE_EMPLOYER_SEARCH_CONFIRM, payload={"title": "X", "role": "Python"}
    )
    cancelled = await sut._handle_employer_search_create_confirm(
        callback=callback,
        actor=actor,
        context=ctx(confirm=False),
    )
    assert cancelled["action"] == "employer_search_create_cancelled"

    sut._conversation_state_service.state = DummyState(
        state_key=STATE_EMPLOYER_SEARCH_CONFIRM, payload={"title": "", "role": ""}
    )
    invalid = await sut._handle_employer_search_create_confirm(
        callback=callback,
        actor=actor,
        context=ctx(confirm=True),
    )
    assert invalid["action"] == "employer_search_confirm_invalid_payload"
