from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.application.bot.constants import ROLE_CANDIDATE, ROLE_EMPLOYER
from app.application.bot.handlers.common.bootstrap import BootstrapRegistrationHandlersMixin
from app.application.bot.handlers.common.stateful_messages import StatefulMessageHandlersMixin


class DummyTelegramClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    async def send_message(self, **kwargs) -> dict:
        self.sent_messages.append(kwargs)
        return {"message_id": len(self.sent_messages), **kwargs}


class DummyAuthSessionService:
    async def get_valid_access_token(self, *, telegram_user_id: int) -> str | None:
        return f"token-for-{telegram_user_id}"


class DummyConversationStateService:
    def __init__(self) -> None:
        self.cleared_for: list[int] = []

    async def clear_state(self, *, telegram_user_id: int) -> None:
        self.cleared_for.append(telegram_user_id)


@dataclass
class DummyActor:
    id: int = 100
    first_name: str | None = "User"


class CandidateBootstrapSut(StatefulMessageHandlersMixin, BootstrapRegistrationHandlersMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self._auth_session_service = DummyAuthSessionService()
        self._candidate_gateway = SimpleNamespace()
        self._conversation_state_service = DummyConversationStateService()

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


class EmployerBootstrapSut(StatefulMessageHandlersMixin, BootstrapRegistrationHandlersMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self._auth_session_service = DummyAuthSessionService()
        self._employer_gateway = SimpleNamespace()
        self._conversation_state_service = DummyConversationStateService()

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

    def _build_idempotency_key(self, **_kwargs) -> str:
        return "idempotency"

    async def _handle_employer_gateway_error(self, **kwargs) -> None:
        raise AssertionError(f"Unexpected employer gateway error: {kwargs}")


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
async def test_candidate_bootstrap_merges_intro_note_into_single_dashboard_message() -> None:
    sut = CandidateBootstrapSut()
    candidate = SimpleNamespace(id="candidate-id")

    async def _get_profile_by_telegram(**_kwargs):
        return candidate

    sut._candidate_gateway.get_profile_by_telegram = _get_profile_by_telegram

    await sut._bootstrap_role(
        actor=DummyActor(),
        chat_id=100,
        role=ROLE_CANDIDATE,
        intro_note="Текущий сценарий отменен. Возвращаю в меню.",
    )

    assert len(sut._telegram_client.sent_messages) == 1
    sent = sut._telegram_client.sent_messages[0]
    assert "Текущий сценарий отменен. Возвращаю в меню." in sent["text"]
    assert "CANDIDATE DASHBOARD" in sent["text"]
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


@pytest.mark.asyncio
async def test_employer_bootstrap_merges_intro_note_into_single_dashboard_message() -> None:
    sut = EmployerBootstrapSut()
    employer = SimpleNamespace(id="employer-id")

    async def _get_by_telegram(**_kwargs):
        return employer

    sut._employer_gateway.get_by_telegram = _get_by_telegram

    await sut._bootstrap_role(
        actor=DummyActor(),
        chat_id=100,
        role=ROLE_EMPLOYER,
        intro_note="Текущий сценарий отменен. Возвращаю в меню.",
    )

    assert len(sut._telegram_client.sent_messages) == 1
    sent = sut._telegram_client.sent_messages[0]
    assert "Текущий сценарий отменен. Возвращаю в меню." in sent["text"]
    assert "EMPLOYER DASHBOARD" in sent["text"]
    assert sent["reply_markup"] == {"employer_for": 100}


@pytest.mark.asyncio
async def test_employer_extended_registration_renders_single_completion_screen() -> None:
    sut = EmployerBootstrapSut()
    employer = SimpleNamespace(id="employer-id")

    async def _get_by_telegram(**_kwargs):
        return employer

    async def _update_employer(**kwargs):
        return SimpleNamespace(id="employer-id", contacts=kwargs["contacts"])

    sut._employer_gateway.get_by_telegram = _get_by_telegram
    sut._employer_gateway.update_employer = _update_employer

    result = await sut._handle_employer_registration_contacts_complete(
        actor=DummyActor(),
        chat_id=100,
        contacts_payload={
            "telegram": "@company",
            "email": "jobs@example.com",
            "phone": None,
            "website": "https://example.com",
        },
    )

    assert result["action"] == "employer_registered_extended"
    assert sut._conversation_state_service.cleared_for == [100]
    assert len(sut._telegram_client.sent_messages) == 1
    sent = sut._telegram_client.sent_messages[0]
    assert sent["text"] == "EMPLOYER DASHBOARD"
    assert sent["reply_markup"] == {"employer_for": 100}
