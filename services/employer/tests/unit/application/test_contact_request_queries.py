from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.common.contracts import CandidateShortProfile
from app.application.employers.queries.get_contact_request_details import (
    GetContactRequestDetailsHandler,
)
from app.application.employers.queries.get_contact_request_status import (
    GetContactRequestStatusHandler,
)
from app.domain.employer.entities import ContactRequest, EmployerProfile
from app.domain.employer.enums import ContactRequestStatus
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


class StubContactRequestsRepo:
    def __init__(self, request: ContactRequest | None) -> None:
        self._request = request

    async def get_by_id(self, request_id):
        if self._request and self._request.id == request_id:
            return self._request
        return None

    async def get_by_employer_and_candidate(self, *, employer_id, candidate_id):
        if (
            self._request
            and self._request.employer_id == employer_id
            and self._request.candidate_id == candidate_id
        ):
            return self._request
        return None


class StubUoW:
    def __init__(self, employer: EmployerProfile | None, request: ContactRequest | None) -> None:
        self.employers = StubEmployersRepo(employer)
        self.contact_requests = StubContactRequestsRepo(request)

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
        contacts_visibility="on_request",
        contacts={"email": "dmitry@example.com"},
        about_me=None,
        explanation=None,
        match_score=0.0,
    )


@pytest.mark.asyncio
async def test_get_contact_request_status_returns_existing(employer) -> None:
    request = ContactRequest.create(
        id=uuid4(),
        employer_id=employer.id,
        candidate_id=uuid4(),
        status=ContactRequestStatus.PENDING,
    )

    def uow_factory():
        return StubUoW(employer, request)

    handler = GetContactRequestStatusHandler(uow_factory=uow_factory)
    result = await handler(
        employer_id=employer.id,
        candidate_id=request.candidate_id,
    )

    assert result.exists is True
    assert result.granted is False
    assert result.request_id == request.id


@pytest.mark.asyncio
async def test_get_contact_request_details_returns_candidate_name(
    employer,
    candidate_profile,
) -> None:
    request = ContactRequest.create(
        id=uuid4(),
        employer_id=employer.id,
        candidate_id=candidate_profile.id,
        status=ContactRequestStatus.PENDING,
    )

    def uow_factory():
        return StubUoW(employer, request)

    handler = GetContactRequestDetailsHandler(
        uow_factory=uow_factory,
        candidate_gateway=StubCandidateGateway(candidate_profile),
    )

    result = await handler(request.id)

    assert result.id == request.id
    assert result.candidate_id == candidate_profile.id
    assert result.candidate_name == "Дмитрий Иванов"
    assert result.employer_telegram_id == 1001
