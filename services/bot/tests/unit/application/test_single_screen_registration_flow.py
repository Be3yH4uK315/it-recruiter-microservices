from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.application.bot.constants import (
    ROLE_CANDIDATE,
    ROLE_EMPLOYER,
    STATE_CANDIDATE_REG_HEADLINE_ROLE,
    STATE_EMPLOYER_REG_COMPANY,
)
from app.application.bot.handlers.common.stateful_messages import StatefulMessageHandlersMixin
from app.application.bot.handlers.common.utils import CommonUtilsMixin
from app.schemas.telegram import TelegramMessage, TelegramUser


@dataclass
class DummyState:
    state_key: str
    role_context: str | None = None
    payload: dict | None = None


class DummyTelegramClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    async def send_message(self, **kwargs) -> dict:
        self.sent_messages.append(kwargs)
        return {"message_id": len(self.sent_messages), **kwargs}


class DummyConversationStateService:
    def __init__(self) -> None:
        self.cleared_for: list[int] = []

    async def clear_state(self, *, telegram_user_id: int) -> None:
        self.cleared_for.append(telegram_user_id)

    async def set_state(self, **_kwargs):
        return None


class DummyAuthSessionService:
    async def get_valid_access_token(self, *, telegram_user_id: int) -> str | None:
        return f"token-for-{telegram_user_id}"


class DummyCandidateGateway:
    def __init__(self) -> None:
        self.profile = SimpleNamespace(id="candidate-id", contacts={"telegram": "@user"})

    async def create_candidate(self, **kwargs):
        self.profile = SimpleNamespace(
            id="candidate-id",
            headline_role=kwargs["headline_role"],
            contacts={"telegram": kwargs["telegram_contact"]},
        )
        return self.profile

    async def get_profile_by_telegram(self, **kwargs):
        return self.profile

    async def update_candidate_profile(self, **kwargs):
        contacts = kwargs.get("contacts")
        self.profile = SimpleNamespace(
            id="candidate-id",
            contacts=contacts,
            location=kwargs.get("location"),
            work_modes=kwargs.get("work_modes"),
            about_me=kwargs.get("about_me"),
            contacts_visibility=kwargs.get("contacts_visibility"),
            salary_min=kwargs.get("salary_min"),
            salary_max=kwargs.get("salary_max"),
            currency=kwargs.get("currency"),
            english_level=kwargs.get("english_level"),
            skills=kwargs.get("skills"),
            education=kwargs.get("education"),
            experiences=kwargs.get("experiences"),
            projects=kwargs.get("projects"),
        )
        return self.profile


class DummyEmployerGateway:
    async def create_employer(self, **kwargs):
        return SimpleNamespace(id="employer-id", company=kwargs["company"])


class CandidateRegistrationSut(CommonUtilsMixin, StatefulMessageHandlersMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self._conversation_state_service = DummyConversationStateService()
        self._auth_session_service = DummyAuthSessionService()
        self._candidate_gateway = DummyCandidateGateway()

    def _log_flow_event(self, *_args, **_kwargs) -> None:
        return None

    def _build_idempotency_key(self, **_kwargs) -> str:
        return "idempotency"

    async def _run_candidate_gateway_call(self, *, operation, **_kwargs):
        return await operation("token")

    async def _safe_get_candidate_statistics(self, **_kwargs):
        return {"views": 5}

    def _build_candidate_dashboard_message(self, **_kwargs) -> str:
        return "CANDIDATE DASHBOARD"

    async def _build_candidate_dashboard_markup(self, telegram_user_id: int):
        return {"dashboard_for": telegram_user_id}

    async def _build_candidate_registration_continue_markup(self, telegram_user_id: int):
        return {"continue_for": telegram_user_id}


class EmployerRegistrationSut(CommonUtilsMixin, StatefulMessageHandlersMixin):
    def __init__(self) -> None:
        self._telegram_client = DummyTelegramClient()
        self._conversation_state_service = DummyConversationStateService()
        self._auth_session_service = DummyAuthSessionService()
        self._employer_gateway = DummyEmployerGateway()

    def _log_flow_event(self, *_args, **_kwargs) -> None:
        return None

    def _build_idempotency_key(self, **_kwargs) -> str:
        return "idempotency"

    async def _run_employer_gateway_call(self, *, operation, **_kwargs):
        return await operation("token")

    async def _safe_get_employer_statistics(self, **_kwargs):
        return {"searches": 2}

    def _build_employer_dashboard_message(self, **_kwargs) -> str:
        return "EMPLOYER DASHBOARD"

    async def _build_employer_registration_continue_markup(self, telegram_user_id: int):
        return {"continue_for": telegram_user_id}


def make_actor() -> TelegramUser:
    return TelegramUser.model_validate({"id": 100, "is_bot": False, "first_name": "User"})


def make_message(text: str) -> TelegramMessage:
    return TelegramMessage.model_validate(
        {
            "message_id": 1,
            "from": {"id": 100, "is_bot": False, "first_name": "User"},
            "chat": {"id": 100, "type": "private"},
            "text": text,
        }
    )


@pytest.mark.asyncio
async def test_candidate_minimal_registration_renders_single_completion_screen() -> None:
    sut = CandidateRegistrationSut()

    result = await sut._handle_stateful_message(
        message=make_message("Python Developer"),
        actor=make_actor(),
        state=DummyState(
            state_key=STATE_CANDIDATE_REG_HEADLINE_ROLE,
            role_context=ROLE_CANDIDATE,
            payload={"display_name": "User"},
        ),
    )

    assert result["action"] == "candidate_registered_minimal"
    assert sut._conversation_state_service.cleared_for == [100]
    assert len(sut._telegram_client.sent_messages) == 1
    sent = sut._telegram_client.sent_messages[0]
    assert "CANDIDATE DASHBOARD" in sent["text"]
    assert "Базовая регистрация завершена." in sent["text"]
    assert sent["reply_markup"] == {"continue_for": 100}


@pytest.mark.asyncio
async def test_employer_minimal_registration_renders_single_completion_screen() -> None:
    sut = EmployerRegistrationSut()

    result = await sut._handle_stateful_message(
        message=make_message("Acme"),
        actor=make_actor(),
        state=DummyState(
            state_key=STATE_EMPLOYER_REG_COMPANY,
            role_context=ROLE_EMPLOYER,
            payload=None,
        ),
    )

    assert result["action"] == "employer_registered_minimal"
    assert sut._conversation_state_service.cleared_for == [100]
    assert len(sut._telegram_client.sent_messages) == 1
    sent = sut._telegram_client.sent_messages[0]
    assert "EMPLOYER DASHBOARD" in sent["text"]
    assert "Базовая регистрация завершена." in sent["text"]
    assert sent["reply_markup"] == {"continue_for": 100}


@pytest.mark.asyncio
async def test_candidate_full_registration_renders_single_completion_screen() -> None:
    sut = CandidateRegistrationSut()

    result = await sut._complete_candidate_full_registration(
        actor=make_actor(),
        chat_id=100,
        payload={
            "location": "Berlin",
            "work_modes": ["remote"],
            "about_me": "About",
            "contacts_visibility": "public",
            "salary_min": 100,
            "salary_max": 200,
            "currency": "EUR",
            "contact_email": "user@example.com",
            "contact_phone": "+123",
            "english_level": "B2",
            "skills": [{"skill": "Python", "kind": "hard", "level": 5}],
            "education": [],
            "experiences": [],
            "projects": [],
        },
    )

    assert result["action"] == "candidate_registered_extended"
    assert sut._conversation_state_service.cleared_for == [100]
    assert len(sut._telegram_client.sent_messages) == 1
    sent = sut._telegram_client.sent_messages[0]
    assert sent["text"] == "CANDIDATE DASHBOARD"
    assert sent["reply_markup"] == {"dashboard_for": 100}
