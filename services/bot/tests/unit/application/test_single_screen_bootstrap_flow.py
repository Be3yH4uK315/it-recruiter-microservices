from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.application.bot.constants import ROLE_CANDIDATE, ROLE_EMPLOYER
from app.application.bot.handlers.common.bootstrap import BootstrapRegistrationHandlersMixin


class DummyTelegramClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    async def send_message(self, **kwargs) -> dict:
        self.sent_messages.append(kwargs)
        return {"message_id": len(self.sent_messages), **kwargs}


class DummyAuthSessionService:
    async def get_valid_access_token(self, *, telegram_user_id: int) -> str | None:
        return f"token-for-{telegram_user_id}"


@dataclass
class DummyActor:
    id: int = 100
    first_name: str | None = "User"


class CandidateBootstrapSut(BootstrapRegistrationHandlersMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self._auth_session_service = DummyAuthSessionService()
        self._candidate_gateway = SimpleNamespace()

    async def _run_candidate_gateway_call(self, *, operation, **_kwargs):
        return await operation("token")

    async def _safe_get_candidate_statistics(self, **_kwargs):
        return {"views": 3}

    def _build_candidate_dashboard_message(self, **_kwargs) -> str:
        return "CANDIDATE DASHBOARD"

    async def _build_candidate_dashboard_markup(self, telegram_user_id: int):
        return {"candidate_for": telegram_user_id}

    async def _recover_pending_uploads_for_role(self, **_kwargs):
        return "RECOVERY NOTE"

    def _log_flow_event(self, *_args, **_kwargs) -> None:
        return None


class EmployerBootstrapSut(BootstrapRegistrationHandlersMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self._auth_session_service = DummyAuthSessionService()
        self._employer_gateway = SimpleNamespace()

    async def _run_employer_gateway_call(self, *, operation, **_kwargs):
        return await operation("token")

    async def _safe_get_employer_statistics(self, **_kwargs):
        return {"searches": 4}

    def _build_employer_dashboard_message(self, **_kwargs) -> str:
        return "EMPLOYER DASHBOARD"

    async def _build_employer_dashboard_markup(self, telegram_user_id: int):
        return {"employer_for": telegram_user_id}

    async def _recover_pending_uploads_for_role(self, **_kwargs):
        return "RECOVERY NOTE"

    def _log_flow_event(self, *_args, **_kwargs) -> None:
        return None


@pytest.mark.asyncio
async def test_candidate_bootstrap_merges_recovery_note_into_single_dashboard_message() -> None:
    sut = CandidateBootstrapSut()
    candidate = SimpleNamespace(id="candidate-id")

    async def _get_profile_by_telegram(**_kwargs):
        return candidate

    sut._candidate_gateway.get_profile_by_telegram = _get_profile_by_telegram

    await sut._bootstrap_role(actor=DummyActor(), chat_id=100, role=ROLE_CANDIDATE)

    assert len(sut._telegram_client.sent_messages) == 1
    sent = sut._telegram_client.sent_messages[0]
    assert "CANDIDATE DASHBOARD" in sent["text"]
    assert "RECOVERY NOTE" in sent["text"]
    assert sent["reply_markup"] == {"candidate_for": 100}


@pytest.mark.asyncio
async def test_employer_bootstrap_merges_recovery_note_into_single_dashboard_message() -> None:
    sut = EmployerBootstrapSut()
    employer = SimpleNamespace(id="employer-id")

    async def _get_by_telegram(**_kwargs):
        return employer

    sut._employer_gateway.get_by_telegram = _get_by_telegram

    await sut._bootstrap_role(actor=DummyActor(), chat_id=100, role=ROLE_EMPLOYER)

    assert len(sut._telegram_client.sent_messages) == 1
    sent = sut._telegram_client.sent_messages[0]
    assert "EMPLOYER DASHBOARD" in sent["text"]
    assert "RECOVERY NOTE" in sent["text"]
    assert sent["reply_markup"] == {"employer_for": 100}
