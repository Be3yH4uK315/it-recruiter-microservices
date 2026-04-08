from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.application.bot.handlers.candidate.dashboard import CandidateDashboardHandlersMixin
from app.application.bot.ui.profile_message_mixins.shared import ProfileSharedMessagesMixin
from app.application.common.contracts import CandidateProfileSummary
from app.application.common.gateway_errors import CandidateGatewayError
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser


@dataclass
class Stats:
    total_views: int = 1
    total_likes: int = 2
    total_contact_requests: int = 3


def make_candidate() -> CandidateProfileSummary:
    return CandidateProfileSummary(
        id=uuid4(),
        telegram_id=100,
        display_name="John",
        headline_role="Python",
        location="Moscow",
        status="active",
        avatar_file_id=None,
        avatar_download_url="https://example.com/a.jpg",
        resume_file_id=None,
        resume_download_url=None,
        version_id=1,
    )


class DummyAuthService:
    def __init__(self, token: str | None = "token") -> None:
        self.token = token

    async def get_valid_access_token(self, *, telegram_user_id: int) -> str | None:
        return self.token


class DummyTelegramClient:
    def __init__(self) -> None:
        self.answered: list[dict] = []

    async def answer_callback_query(self, **kwargs) -> None:
        self.answered.append(kwargs)


class DummyCandidateGateway:
    def __init__(
        self, candidate: CandidateProfileSummary | None = None, raise_error: bool = False
    ) -> None:
        self.candidate = candidate
        self.raise_error = raise_error

    async def get_profile_by_telegram(self, *, access_token: str, telegram_id: int):
        if self.raise_error:
            raise CandidateGatewayError("failed")
        return self.candidate


class DummyCandidateDashboard(CandidateDashboardHandlersMixin, ProfileSharedMessagesMixin):
    def __init__(
        self,
        *,
        token: str | None = "token",
        candidate: CandidateProfileSummary | None = None,
        raise_error: bool = False,
    ) -> None:
        self._auth_session_service = DummyAuthService(token)
        self._telegram_client = DummyTelegramClient()
        self._candidate_gateway = DummyCandidateGateway(candidate, raise_error)
        self.calls: list[tuple[str, dict]] = []

    async def _expired_session_callback(self, callback):
        self.calls.append(("_expired_session_callback", {"callback": callback}))

    async def _run_candidate_gateway_call(
        self, *, telegram_user_id: int, access_token: str, operation
    ):
        return await operation(access_token)

    async def _answer_callback_and_handle_gateway_error(self, **kwargs):
        self.calls.append(("_answer_callback_and_handle_gateway_error", kwargs))

    async def _send_retry_action_if_temporarily_unavailable(self, **kwargs):
        self.calls.append(("_send_retry_action_if_temporarily_unavailable", kwargs))

    def _resolve_chat_id(self, callback, actor) -> int:
        return actor.id

    async def _render_callback_screen_with_optional_photo(self, **kwargs):
        self.calls.append(("_render_callback_screen_with_optional_photo", kwargs))

    async def _render_callback_screen(self, **kwargs):
        self.calls.append(("_render_callback_screen", kwargs))

    def _build_candidate_profile_message(self, *, candidate: CandidateProfileSummary) -> str:
        return f"profile:{candidate.display_name}"

    async def _build_candidate_profile_view_markup(
        self, *, telegram_user_id: int, candidate: CandidateProfileSummary
    ):
        return {"telegram_user_id": telegram_user_id}

    async def _safe_get_candidate_statistics(self, *, access_token: str, candidate_id):
        return Stats()

    def _build_candidate_dashboard_message(self, **kwargs) -> str:
        return "dashboard"

    async def _build_candidate_dashboard_markup(self, telegram_user_id: int):
        return {"uid": telegram_user_id}

    async def _build_candidate_profile_edit_menu_markup(self, *, telegram_user_id: int):
        return {"uid": telegram_user_id}

    async def _build_candidate_files_section_markup(self, **kwargs):
        return {"files": True}

    async def _build_candidate_contacts_section_markup(self, **kwargs):
        return {"contacts": True}

    def _humanize_candidate_status(self, value: str | None) -> str:
        return value or "—"


def make_callback_actor() -> tuple[TelegramCallbackQuery, TelegramUser]:
    callback = TelegramCallbackQuery.model_validate(
        {
            "id": "cb1",
            "from": {"id": 100, "is_bot": False, "first_name": "User"},
            "data": "x",
        }
    )
    actor = TelegramUser.model_validate({"id": 100, "is_bot": False, "first_name": "User"})
    return callback, actor


@pytest.mark.asyncio
async def test_candidate_profile_session_expired() -> None:
    callback, actor = make_callback_actor()
    sut = DummyCandidateDashboard(token=None)

    result = await sut._handle_candidate_profile(callback=callback, actor=actor)

    assert result == {"status": "processed", "action": "session_expired"}


@pytest.mark.asyncio
async def test_candidate_profile_gateway_error() -> None:
    callback, actor = make_callback_actor()
    sut = DummyCandidateDashboard(candidate=None, raise_error=True)

    result = await sut._handle_candidate_profile(callback=callback, actor=actor)

    assert result == {"status": "processed", "action": "candidate_gateway_error"}


@pytest.mark.asyncio
async def test_candidate_profile_not_found() -> None:
    callback, actor = make_callback_actor()
    sut = DummyCandidateDashboard(candidate=None)

    result = await sut._handle_candidate_profile(callback=callback, actor=actor)

    assert result == {"status": "processed", "action": "candidate_not_found"}


@pytest.mark.asyncio
async def test_candidate_profile_happy_path() -> None:
    callback, actor = make_callback_actor()
    sut = DummyCandidateDashboard(candidate=make_candidate())

    result = await sut._handle_candidate_profile(callback=callback, actor=actor)

    assert result == {"status": "processed", "action": "candidate_profile"}
    assert any(name == "_render_callback_screen_with_optional_photo" for name, _ in sut.calls)


@pytest.mark.asyncio
async def test_candidate_dashboard_and_menus_happy_paths() -> None:
    callback, actor = make_callback_actor()
    sut = DummyCandidateDashboard(candidate=make_candidate())

    dashboard = await sut._handle_candidate_dashboard(callback=callback, actor=actor)
    profile_edit_menu = await sut._handle_candidate_profile_edit_menu(
        callback=callback, actor=actor
    )
    files_section = await sut._handle_candidate_open_files_section(callback=callback, actor=actor)

    assert dashboard == {"status": "processed", "action": "candidate_dashboard"}
    assert profile_edit_menu == {"status": "processed", "action": "candidate_profile_edit_menu"}
    assert files_section == {"status": "processed", "action": "candidate_menu_open_files_section"}
    render_calls = [payload for name, payload in sut.calls if name == "_render_callback_screen"]
    assert any("Редактирование профиля кандидата" in call["text"] for call in render_calls)
    assert any("Файлы кандидата" in call["text"] for call in render_calls)
