from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.bot.handlers.candidate.file_contact import CandidateFileContactHandlersMixin
from app.application.common.contracts import CandidateProfileSummary
from app.application.common.gateway_errors import CandidateGatewayError
from app.schemas.telegram import TelegramCallbackQuery, TelegramUser


class DummyAuthService:
    def __init__(self, token: str | None = "token") -> None:
        self.token = token

    async def get_valid_access_token(self, *, telegram_user_id: int) -> str | None:
        return self.token


class DummyTelegramClient:
    def __init__(self) -> None:
        self.answered: list[dict] = []

    async def answer_callback_query(self, **kwargs):
        self.answered.append(kwargs)


class DummyCandidateGateway:
    def __init__(self) -> None:
        self.raise_error = False
        self.candidate: CandidateProfileSummary | None = CandidateProfileSummary(
            id=uuid4(),
            telegram_id=100,
            display_name="John",
            headline_role="Python",
            location="Moscow",
            status="active",
            avatar_file_id=None,
            avatar_download_url="https://example.com/avatar.jpg",
            resume_file_id=None,
            resume_download_url="https://example.com/resume.pdf",
            version_id=1,
        )

    async def get_profile_by_telegram(self, *, access_token: str, telegram_id: int):
        if self.raise_error:
            raise CandidateGatewayError("boom")
        return self.candidate

    async def delete_avatar(self, *, access_token: str, candidate_id, idempotency_key: str):
        if self.raise_error:
            raise CandidateGatewayError("boom")

    async def delete_resume(self, *, access_token: str, candidate_id, idempotency_key: str):
        if self.raise_error:
            raise CandidateGatewayError("boom")


class DummyCandidateFiles(CandidateFileContactHandlersMixin):
    def __init__(self) -> None:
        self._auth_session_service = DummyAuthService()
        self._telegram_client = DummyTelegramClient()
        self._candidate_gateway = DummyCandidateGateway()
        self.calls: list[tuple[str, dict]] = []

    async def _run_candidate_gateway_call(
        self, *, telegram_user_id: int, access_token: str, operation
    ):
        return await operation(access_token)

    async def _expired_session_callback(self, callback):
        self.calls.append(("expired", {"callback": callback}))

    async def _answer_callback_and_handle_gateway_error(self, **kwargs):
        self.calls.append(("gateway_error", kwargs))

    async def _safe_get_candidate_statistics(self, **kwargs):
        return {"views": 1}

    async def _build_candidate_dashboard_markup(self, telegram_user_id: int):
        return {"dashboard": telegram_user_id}

    def _build_candidate_dashboard_message(self, **kwargs) -> str:
        return "candidate-dashboard"

    async def _render_callback_screen(self, **kwargs):
        self.calls.append(("render", kwargs))

    def _build_idempotency_key(self, **_kwargs) -> str:
        return "idempotency"


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


@pytest.mark.asyncio
async def test_candidate_delete_file_renders_updated_screen_in_place() -> None:
    sut = DummyCandidateFiles()
    callback = make_callback()
    actor = make_actor()

    avatar_result = await sut._handle_candidate_delete_file(
        callback=callback, actor=actor, target_kind="avatar"
    )
    resume_result = await sut._handle_candidate_delete_file(
        callback=callback, actor=actor, target_kind="resume"
    )

    assert avatar_result["action"] == "candidate_avatar_deleted"
    assert resume_result["action"] == "candidate_resume_deleted"
    render_calls = [payload for name, payload in sut.calls if name == "render"]
    assert len(render_calls) == 2
    assert "Аватар удалён." in render_calls[0]["text"]
    assert "Резюме удалено." in render_calls[1]["text"]
    assert all(call["reply_markup"] == {"dashboard": 100} for call in render_calls)
