from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.common.contracts import CandidateShortProfile
from app.application.employers.queries.get_favorites import GetFavoritesHandler
from app.application.employers.queries.get_unlocked_contacts import GetUnlockedContactsHandler
from app.domain.employer.entities import EmployerProfile
from app.domain.employer.value_objects import EmployerContacts


class StubCandidateGateway:
    def __init__(self, profiles: dict[str, CandidateShortProfile]) -> None:
        self._profiles = profiles

    async def get_candidate_profile(self, *, candidate_id, employer_telegram_id):
        return self._profiles.get(str(candidate_id))


class StubEmployersRepo:
    def __init__(self, employer: EmployerProfile | None) -> None:
        self._employer = employer

    async def get_by_id(self, employer_id):
        return self._employer


class StubSearchesRepo:
    def __init__(self, favorite_ids: list, unlocked_ids: list) -> None:
        self._favorite_ids = favorite_ids
        self._unlocked_ids = unlocked_ids

    async def list_favorite_candidate_ids(self, employer_id):
        return self._favorite_ids

    async def list_unlocked_candidate_ids(self, employer_id):
        return self._unlocked_ids


class StubContactRequestsRepo:
    def __init__(self, unlocked_ids: list) -> None:
        self._unlocked_ids = unlocked_ids

    async def list_unlocked_candidate_ids(self, employer_id):
        return self._unlocked_ids


class StubUoW:
    def __init__(
        self,
        employer: EmployerProfile | None,
        favorite_ids: list,
        unlocked_ids: list,
    ) -> None:
        self.employers = StubEmployersRepo(employer)
        self.searches = StubSearchesRepo(favorite_ids, unlocked_ids)
        self.contact_requests = StubContactRequestsRepo(unlocked_ids)

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
async def test_get_favorites_returns_profiles(employer, candidate_profile) -> None:
    profiles = {str(candidate_profile.id): candidate_profile}

    def uow_factory():
        return StubUoW(employer, [candidate_profile.id], [])

    handler = GetFavoritesHandler(
        uow_factory=uow_factory,
        candidate_gateway=StubCandidateGateway(profiles),
    )

    result = await handler(employer.id)

    assert len(result) == 1
    assert result[0].id == candidate_profile.id


@pytest.mark.asyncio
async def test_get_unlocked_contacts_returns_profiles(employer, candidate_profile) -> None:
    profiles = {str(candidate_profile.id): candidate_profile}

    def uow_factory():
        return StubUoW(employer, [], [candidate_profile.id])

    handler = GetUnlockedContactsHandler(
        uow_factory=uow_factory,
        candidate_gateway=StubCandidateGateway(profiles),
    )

    result = await handler(employer.id)

    assert len(result) == 1
    assert result[0].id == candidate_profile.id
