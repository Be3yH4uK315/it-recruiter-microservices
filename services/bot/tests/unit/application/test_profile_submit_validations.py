from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.bot.handlers.candidate.profile_submit import (
    CandidateProfileSubmitHandlersMixin,
)
from app.application.bot.handlers.common.utils import CommonUtilsMixin
from app.application.bot.handlers.employer.profile_submit import (
    EmployerProfileSubmitHandlersMixin,
)
from app.application.common.contracts import CandidateProfileSummary, EmployerProfileSummary
from app.schemas.telegram import TelegramUser


class DummyTelegramClient:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, **kwargs) -> None:
        self.messages.append(kwargs)


class DummyAuthSessionService:
    def __init__(self, token: str | None = "token") -> None:
        self.token = token

    async def get_valid_access_token(self, *, telegram_user_id: int) -> str | None:
        return self.token


class DummyCandidateGateway:
    def __init__(self, candidate: CandidateProfileSummary) -> None:
        self.candidate = candidate

    async def get_profile_by_telegram(self, *, access_token: str, telegram_id: int):
        return self.candidate


class DummyEmployerGateway:
    def __init__(self, employer: EmployerProfileSummary) -> None:
        self.employer = employer

    async def get_by_telegram(self, *, access_token: str, telegram_id: int):
        return self.employer


class ValidationSut(
    CandidateProfileSubmitHandlersMixin,
    EmployerProfileSubmitHandlersMixin,
    CommonUtilsMixin,
):
    def __init__(self) -> None:
        self._auth_session_service = DummyAuthSessionService()
        self._telegram_client = DummyTelegramClient()
        self._conversation_state_service = object()
        self._candidate_gateway = DummyCandidateGateway(
            CandidateProfileSummary(
                id=uuid4(),
                telegram_id=100,
                display_name="Alice",
                headline_role="Developer",
                location=None,
                status=None,
                avatar_file_id=None,
                avatar_download_url=None,
                resume_file_id=None,
                resume_download_url=None,
                version_id=1,
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
                contacts={},
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


def make_actor() -> TelegramUser:
    return TelegramUser.model_validate({"id": 100, "is_bot": False, "first_name": "User"})


@pytest.mark.asyncio
async def test_candidate_display_name_rejects_punctuation_only_input() -> None:
    sut = ValidationSut()

    result = await sut._handle_candidate_edit_submit(
        actor=make_actor(),
        chat_id=100,
        field_name="display_name",
        raw_value=".",
    )

    assert result["action"] == "candidate_edit_display_name_invalid"
    assert sut._telegram_client.messages[0]["text"].startswith(
        "Отображаемое имя должно быть не короче 2 символов."
    )
    assert "Иван Петров" in sut._telegram_client.messages[0]["text"]


@pytest.mark.asyncio
async def test_employer_company_rejects_punctuation_only_input() -> None:
    sut = ValidationSut()

    result = await sut._handle_employer_edit_company_submit(
        actor=make_actor(),
        chat_id=100,
        company=".",
    )

    assert result["action"] == "employer_edit_company_invalid"
    assert sut._telegram_client.messages[0]["text"].startswith(
        "Название компании должно быть не короче 2 символов."
    )
    assert "Acme Labs" in sut._telegram_client.messages[0]["text"]


@pytest.mark.asyncio
async def test_employer_website_rejects_broken_url() -> None:
    sut = ValidationSut()

    result = await sut._handle_employer_contact_submit(
        actor=make_actor(),
        chat_id=100,
        contact_key="website",
        raw_value="https://.",
    )

    assert result["action"] == "employer_contact_invalid"
    assert sut._telegram_client.messages[0]["text"].startswith("Некорректный сайт.")
    assert "http://" in sut._telegram_client.messages[0]["text"]
