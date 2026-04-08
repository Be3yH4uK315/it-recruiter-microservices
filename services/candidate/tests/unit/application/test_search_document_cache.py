from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.candidates.queries.get_candidate_search_document import (
    GetCandidateSearchDocumentHandler,
    clear_candidate_search_document_cache,
)
from app.application.candidates.queries.list_candidate_search_documents import (
    ListCandidateSearchDocumentsHandler,
    clear_candidate_search_document_list_cache,
)
from app.domain.candidate.entities import CandidateProfile
from app.domain.candidate.enums import CandidateStatus, ContactsVisibility, WorkMode


class StubCandidateRepository:
    def __init__(self, candidate: CandidateProfile) -> None:
        self._candidate = candidate
        self.get_by_id_calls = 0
        self.list_for_search_calls = 0

    async def get_by_id(self, candidate_id):
        self.get_by_id_calls += 1
        if candidate_id == self._candidate.id:
            return self._candidate
        return None

    async def list_for_search(self, *, limit: int = 100, offset: int = 0):
        _ = (limit, offset)
        self.list_for_search_calls += 1
        return [self._candidate]


class StubUnitOfWork:
    def __init__(self, candidate: CandidateProfile) -> None:
        self.candidates = StubCandidateRepository(candidate)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.fixture(autouse=True)
def clear_search_document_caches() -> None:
    clear_candidate_search_document_cache()
    clear_candidate_search_document_list_cache()


@pytest.fixture
def cached_candidate() -> CandidateProfile:
    return CandidateProfile.create(
        id=uuid4(),
        telegram_id=42,
        display_name="Load Test Candidate",
        headline_role="Python Developer",
        location="Berlin",
        work_modes=[WorkMode.REMOTE],
        contacts_visibility=ContactsVisibility.ON_REQUEST,
        contacts={"telegram": "@candidate"},
        status=CandidateStatus.ACTIVE,
        english_level=None,
        about_me=None,
        salary_range=None,
        skills=[],
        education=[],
        experiences=[],
        projects=[],
    )


@pytest.mark.asyncio
async def test_get_candidate_search_document_uses_cache(cached_candidate: CandidateProfile) -> None:
    uow = StubUnitOfWork(cached_candidate)
    handler = GetCandidateSearchDocumentHandler(
        lambda: uow,
        cache_ttl_seconds=60.0,
    )

    first = await handler(cached_candidate.id)
    second = await handler(cached_candidate.id)

    assert first == second
    assert uow.candidates.get_by_id_calls == 1


@pytest.mark.asyncio
async def test_list_candidate_search_documents_uses_cache(
    cached_candidate: CandidateProfile,
) -> None:
    uow = StubUnitOfWork(cached_candidate)
    handler = ListCandidateSearchDocumentsHandler(
        lambda: uow,
        cache_ttl_seconds=60.0,
    )

    first = await handler(limit=50, offset=0)
    second = await handler(limit=50, offset=0)

    assert first == second
    assert len(first) == 1
    assert uow.candidates.list_for_search_calls == 1
