from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.common.contracts import CandidateShortProfile
from app.application.employers.commands.request_contact_access import (
    RequestContactAccessCommand,
    RequestContactAccessHandler,
)
from app.application.employers.queries.has_contact_access import HasContactAccessHandler
from app.domain.employer.entities import ContactRequest, EmployerProfile
from app.domain.employer.value_objects import EmployerContacts


class StubCandidateGateway:
    def __init__(self, profile: CandidateShortProfile | None) -> None:
        self._profile = profile

    async def get_candidate_profile(self, *, candidate_id, employer_telegram_id):
        return self._profile


class StubEmployersRepo:
    def __init__(self, employer: EmployerProfile | None) -> None:
        self._employer = employer

    async def get_by_id(self, employer_id):
        return self._employer

    async def get_by_telegram_id(self, telegram_id):
        if self._employer and self._employer.telegram_id == telegram_id:
            return self._employer
        return None


class StubContactRequestsRepo:
    def __init__(self) -> None:
        self.request: ContactRequest | None = None

    async def get_by_employer_and_candidate(self, *, employer_id, candidate_id):
        if (
            self.request is not None
            and self.request.employer_id == employer_id
            and self.request.candidate_id == candidate_id
        ):
            return self.request
        return None

    async def add(self, request):
        self.request = request

    async def save(self, request):
        self.request = request


class StubOutbox:
    async def publish(self, *, routing_key: str, payload: dict) -> None:
        return None


class StubEventMapper:
    def map_domain_event(self, *, event, employer=None, contact_request=None):
        return []


class StubUoW:
    def __init__(
        self, employer: EmployerProfile | None, request_repo: StubContactRequestsRepo
    ) -> None:
        self.employers = StubEmployersRepo(employer)
        self.contact_requests = request_repo
        self.outbox = StubOutbox()
        self.event_mapper = StubEventMapper()
        self.searches = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None


@pytest.fixture
def employer() -> EmployerProfile:
    return EmployerProfile.create(
        id=uuid4(),
        telegram_id=1001,
        company="Acme",
        contacts=EmployerContacts(email="hr@acme.test"),
    )


@pytest.fixture
def candidate_profile() -> CandidateShortProfile:
    return CandidateShortProfile(
        id=uuid4(),
        display_name="Дмитрий Иванов",
        headline_role="Python Developer",
        location="Paris",
        work_modes=["remote"],
        experience_years=4.0,
        skills=[{"skill": "python", "level": 5}],
        salary_min=200000,
        salary_max=300000,
        currency="RUB",
        english_level="B2",
        contacts_visibility="public",
        contacts={"email": "dmitry@example.com"},
        about_me=None,
        explanation=None,
        match_score=0.0,
    )


@pytest.mark.asyncio
async def test_request_contact_access_grants_for_public_candidate(
    employer, candidate_profile
) -> None:
    request_repo = StubContactRequestsRepo()

    def uow_factory():
        return StubUoW(employer, request_repo)

    handler = RequestContactAccessHandler(
        uow_factory=uow_factory,
        candidate_gateway=StubCandidateGateway(candidate_profile),
    )

    result = await handler(
        RequestContactAccessCommand(
            employer_id=employer.id,
            candidate_id=candidate_profile.id,
        )
    )

    assert result.granted is True
    assert result.contacts == {"email": "dmitry@example.com"}
    assert request_repo.request is not None
    assert request_repo.request.granted is True


@pytest.mark.asyncio
async def test_has_contact_access_returns_false_when_missing_request(employer) -> None:
    request_repo = StubContactRequestsRepo()

    def uow_factory():
        return StubUoW(employer, request_repo)

    handler = HasContactAccessHandler(uow_factory=uow_factory)
    result = await handler(
        candidate_id=uuid4(),
        employer_telegram_id=1001,
    )
    assert result is False
