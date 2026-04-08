from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from app.application.bot.handlers.candidate.profile_submit import (
    CandidateProfileSubmitHandlersMixin,
)
from app.application.bot.handlers.common.utils import CommonUtilsMixin
from app.application.bot.handlers.employer.profile_submit import (
    EmployerProfileSubmitHandlersMixin,
)
from app.application.common.contracts import (
    UNSET,
    CandidateProfileSummary,
    EmployerProfileSummary,
)
from app.schemas.telegram import TelegramUser


class DummyTelegramClient:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, **kwargs) -> None:
        self.messages.append(kwargs)


class DummyConversationStateService:
    def __init__(self) -> None:
        self.cleared: list[int] = []

    async def clear_state(self, *, telegram_user_id: int) -> None:
        self.cleared.append(telegram_user_id)


class DummyAuthSessionService:
    def __init__(self, token: str | None = "token") -> None:
        self.token = token

    async def get_valid_access_token(self, *, telegram_user_id: int) -> str | None:
        return self.token


class DummyCandidateGateway:
    def __init__(self, candidate: CandidateProfileSummary) -> None:
        self.candidate = candidate
        self.last_update_kwargs: dict | None = None

    async def get_profile_by_telegram(self, *, access_token: str, telegram_id: int):
        return self.candidate

    async def update_candidate_profile(self, **kwargs):
        self.last_update_kwargs = kwargs
        update_fields = {
            key: value
            for key, value in kwargs.items()
            if key not in {"access_token", "candidate_id", "idempotency_key"} and value is not UNSET
        }
        self.candidate = replace(self.candidate, **update_fields)
        return self.candidate


class DummyEmployerGateway:
    def __init__(self, employer: EmployerProfileSummary) -> None:
        self.employer = employer
        self.last_update_kwargs: dict | None = None

    async def get_by_telegram(self, *, access_token: str, telegram_id: int):
        return self.employer

    async def update_employer(self, **kwargs):
        self.last_update_kwargs = kwargs
        update_fields = {
            key: value
            for key, value in kwargs.items()
            if key not in {"access_token", "employer_id", "idempotency_key"}
        }
        self.employer = replace(self.employer, **update_fields)
        return self.employer


class SuccessSut(
    CandidateProfileSubmitHandlersMixin,
    EmployerProfileSubmitHandlersMixin,
    CommonUtilsMixin,
):
    def __init__(self) -> None:
        self._auth_session_service = DummyAuthSessionService()
        self._telegram_client = DummyTelegramClient()
        self._conversation_state_service = DummyConversationStateService()
        self._candidate_gateway = DummyCandidateGateway(
            CandidateProfileSummary(
                id=uuid4(),
                telegram_id=100,
                display_name="Alice",
                headline_role="Developer",
                location="Moscow",
                status="active",
                avatar_file_id=None,
                avatar_download_url=None,
                resume_file_id=None,
                resume_download_url=None,
                version_id=1,
                contacts={"telegram": "@alice"},
                skills=[{"skill": "Python", "kind": "hard", "level": 5}],
            )
        )
        self._employer_gateway = DummyEmployerGateway(
            EmployerProfileSummary(
                id=uuid4(),
                telegram_id=100,
                company="Acme",
                avatar_file_id=None,
                avatar_download_url=None,
                document_file_id=None,
                document_download_url=None,
                contacts={"email": "jobs@acme.test"},
            )
        )

    async def _run_candidate_gateway_call(
        self, *, telegram_user_id: int, access_token: str, operation
    ):
        return await operation(access_token)

    async def _run_employer_gateway_call(
        self, *, telegram_user_id: int, access_token: str, operation
    ):
        return await operation(access_token)

    async def _safe_get_candidate_statistics(self, **kwargs):
        return {"views": 3}

    async def _safe_get_employer_statistics(self, **kwargs):
        return {"total": 2}

    async def _build_candidate_dashboard_markup(self, telegram_user_id: int):
        return {"candidate_dashboard": telegram_user_id}

    async def _build_employer_dashboard_markup(self, telegram_user_id: int):
        return {"employer_dashboard": telegram_user_id}

    def _build_candidate_dashboard_message(self, **kwargs) -> str:
        candidate = kwargs["candidate"]
        return f"candidate-dashboard:{candidate.display_name}:{candidate.location}"

    def _build_employer_dashboard_message(self, **kwargs) -> str:
        employer = kwargs["employer"]
        return f"employer-dashboard:{employer.company}"

    def _build_idempotency_key(self, **kwargs) -> str:
        return f"idempotency:{kwargs['operation']}"

    async def _handle_candidate_gateway_error(self, **kwargs) -> None:
        raise AssertionError(f"Unexpected candidate gateway error: {kwargs}")

    async def _handle_employer_gateway_error(self, **kwargs) -> None:
        raise AssertionError(f"Unexpected employer gateway error: {kwargs}")


def make_actor() -> TelegramUser:
    return TelegramUser.model_validate({"id": 100, "is_bot": False, "first_name": "User"})


@pytest.mark.asyncio
async def test_candidate_edit_submit_renders_single_dashboard_screen() -> None:
    sut = SuccessSut()

    result = await sut._handle_candidate_edit_submit(
        actor=make_actor(),
        chat_id=100,
        field_name="location",
        raw_value="Berlin",
    )

    assert result["action"] == "candidate_edit_location_saved"
    assert sut._candidate_gateway.last_update_kwargs is not None
    assert sut._candidate_gateway.last_update_kwargs["location"] == "Berlin"
    assert sut._conversation_state_service.cleared == [100]
    assert sut._telegram_client.messages == [
        {
            "chat_id": 100,
            "text": "candidate-dashboard:Alice:Berlin",
            "parse_mode": "Markdown",
            "reply_markup": {"candidate_dashboard": 100},
        }
    ]


@pytest.mark.asyncio
async def test_candidate_contact_submit_renders_single_dashboard_screen() -> None:
    sut = SuccessSut()

    result = await sut._handle_candidate_contact_submit(
        actor=make_actor(),
        chat_id=100,
        contact_key="email",
        raw_value="alice@example.com",
        allow_clear=True,
    )

    assert result["action"] == "candidate_edit_contact_email_saved"
    assert sut._candidate_gateway.last_update_kwargs is not None
    assert sut._candidate_gateway.last_update_kwargs["contacts"] == {
        "telegram": "@alice",
        "email": "alice@example.com",
    }
    assert sut._conversation_state_service.cleared == [100]
    assert sut._telegram_client.messages == [
        {
            "chat_id": 100,
            "text": "candidate-dashboard:Alice:Moscow",
            "parse_mode": "Markdown",
            "reply_markup": {"candidate_dashboard": 100},
        }
    ]


@pytest.mark.asyncio
async def test_employer_edit_company_submit_renders_single_dashboard_screen() -> None:
    sut = SuccessSut()

    result = await sut._handle_employer_edit_company_submit(
        actor=make_actor(),
        chat_id=100,
        company="Acme Labs",
    )

    assert result["action"] == "employer_edit_company_saved"
    assert sut._employer_gateway.last_update_kwargs is not None
    assert sut._employer_gateway.last_update_kwargs["company"] == "Acme Labs"
    assert sut._conversation_state_service.cleared == [100]
    assert sut._telegram_client.messages == [
        {
            "chat_id": 100,
            "text": "employer-dashboard:Acme Labs",
            "parse_mode": "Markdown",
            "reply_markup": {"employer_dashboard": 100},
        }
    ]


@pytest.mark.asyncio
async def test_employer_contact_submit_renders_single_dashboard_screen() -> None:
    sut = SuccessSut()

    result = await sut._handle_employer_contact_submit(
        actor=make_actor(),
        chat_id=100,
        contact_key="website",
        raw_value="https://acme.test",
    )

    assert result["action"] == "employer_edit_contact_website_saved"
    assert sut._employer_gateway.last_update_kwargs is not None
    assert sut._employer_gateway.last_update_kwargs["contacts"] == {
        "email": "jobs@acme.test",
        "website": "https://acme.test",
    }
    assert sut._conversation_state_service.cleared == [100]
    assert sut._telegram_client.messages == [
        {
            "chat_id": 100,
            "text": "employer-dashboard:Acme",
            "parse_mode": "Markdown",
            "reply_markup": {"employer_dashboard": 100},
        }
    ]
