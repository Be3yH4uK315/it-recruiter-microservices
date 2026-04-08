from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.http.v1.api import api_router
from app.api.http.v1.dependencies import (
    get_delete_candidate_document_handler,
    get_get_candidate_document_handler,
    get_rebuild_indices_handler,
    get_search_candidates_handler,
    get_upsert_candidate_document_handler,
)
from app.application.search.dto.views import (
    CandidateSearchHitView,
    IndexedCandidateDocumentView,
    RebuildIndicesView,
    SearchCandidatesView,
)
from app.domain.search.errors import CandidateDocumentNotFoundError
from app.infrastructure.web.exception_handlers import register_exception_handlers
from app.infrastructure.web.middleware.request_id import RequestIdMiddleware


class FakeSearchCandidatesHandler:
    def __init__(self) -> None:
        self.calls = []

    async def __call__(self, query) -> SearchCandidatesView:
        self.calls.append(query)
        return SearchCandidatesView(
            total=1,
            items=[
                CandidateSearchHitView(
                    candidate_id=uuid4(),
                    display_name="Ivan",
                    headline_role="Python Developer",
                    experience_years=4.0,
                    location="Paris",
                    skills=[{"skill": "python"}],
                    salary_min=100000,
                    salary_max=150000,
                    currency="RUB",
                    english_level="B2",
                    about_me="Async backend",
                    match_score=0.95,
                    explanation={"source": "test"},
                )
            ],
        )


class FakeRebuildIndicesHandler:
    def __init__(self) -> None:
        self.calls = []

    async def __call__(self, command) -> RebuildIndicesView:
        self.calls.append(command)
        return RebuildIndicesView(
            processed=2,
            indexed=2,
            skipped=0,
            failed=0,
        )


class FakeUpsertCandidateDocumentHandler:
    def __init__(self) -> None:
        self.calls = []

    async def __call__(self, command) -> IndexedCandidateDocumentView:
        self.calls.append(command)
        return IndexedCandidateDocumentView(
            candidate_id=command.candidate_id,
            searchable_text="Python Developer Ivan",
            document={
                "id": str(command.candidate_id),
                "display_name": "Ivan",
                "headline_role": "Python Developer",
            },
            vector_present=True,
            vector_store="milvus",
        )


class FakeDeleteCandidateDocumentHandler:
    def __init__(self) -> None:
        self.calls = []

    async def __call__(self, command) -> bool:
        self.calls.append(command)
        return True


class FakeGetCandidateDocumentHandler:
    def __init__(self, *, should_raise: bool = False) -> None:
        self.calls = []
        self.should_raise = should_raise

    async def __call__(self, candidate_id):
        self.calls.append(candidate_id)
        if self.should_raise:
            raise CandidateDocumentNotFoundError(
                f"candidate document {candidate_id} not found",
            )
        return IndexedCandidateDocumentView(
            candidate_id=candidate_id,
            searchable_text="Python Developer Ivan",
            document={
                "id": str(candidate_id),
                "display_name": "Ivan",
                "headline_role": "Python Developer",
            },
            vector_present=True,
            vector_store="milvus",
        )


class FakeResourceRegistry:
    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready

    async def get_health_snapshot(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "components": {
                "elasticsearch": {"status": "ok" if self.ready else "unavailable"},
                "milvus": {"status": "ok" if self.ready else "unavailable"},
                "embedding_provider": {"status": "ok" if self.ready else "not_initialized"},
                "ranker": {"status": "ok" if self.ready else "not_initialized"},
                "indexing_service": {"status": "ok" if self.ready else "not_initialized"},
                "hybrid_search_service": {"status": "ok" if self.ready else "not_initialized"},
            },
        }


@pytest.fixture()
def app(monkeypatch) -> FastAPI:
    fake_settings = SimpleNamespace(
        app_name="search-service",
        app_version="0.1.0",
        app_env="test",
        internal_service_token="super-secret-internal-token",
        request_id_header_name="X-Request-ID",
        expose_request_id_header=True,
    )
    monkeypatch.setattr(
        "app.infrastructure.auth.internal.get_settings",
        lambda: fake_settings,
    )

    application = FastAPI()
    application.add_middleware(RequestIdMiddleware, settings=fake_settings)
    application.include_router(api_router)
    register_exception_handlers(application)
    application.state.settings = fake_settings
    application.state.resource_registry = FakeResourceRegistry()
    return application


@pytest.fixture()
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as async_client:
        yield async_client


@pytest.fixture()
def fake_handlers(app: FastAPI) -> dict[str, object]:
    handlers = {
        "search": FakeSearchCandidatesHandler(),
        "rebuild": FakeRebuildIndicesHandler(),
        "upsert": FakeUpsertCandidateDocumentHandler(),
        "delete": FakeDeleteCandidateDocumentHandler(),
        "get": FakeGetCandidateDocumentHandler(),
    }

    app.dependency_overrides[get_search_candidates_handler] = lambda: handlers["search"]
    app.dependency_overrides[get_rebuild_indices_handler] = lambda: handlers["rebuild"]
    app.dependency_overrides[get_upsert_candidate_document_handler] = lambda: handlers["upsert"]
    app.dependency_overrides[get_delete_candidate_document_handler] = lambda: handlers["delete"]
    app.dependency_overrides[get_get_candidate_document_handler] = lambda: handlers["get"]

    return handlers


@pytest.mark.asyncio
async def test_healthcheck(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "search-service"


@pytest.mark.asyncio
async def test_healthcheck_returns_503_when_registry_not_ready(app: FastAPI) -> None:
    app.state.resource_registry = FakeResourceRegistry(ready=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["components"]["elasticsearch"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_search_candidates(client: AsyncClient, fake_handlers: dict[str, object]) -> None:
    response = await client.post(
        "/api/v1/search/candidates",
        headers={"Authorization": "Bearer super-secret-internal-token"},
        json={
            "filters": {
                "role": "Python Developer",
                "must_skills": [{"skill": "Python", "level": 5}],
                "location": "Paris",
            },
            "limit": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["display_name"] == "Ivan"
    assert body["items"][0]["headline_role"] == "Python Developer"
    assert body["items"][0]["match_score"] == 0.95


@pytest.mark.asyncio
async def test_search_candidates_requires_auth(
    client: AsyncClient, fake_handlers: dict[str, object]
) -> None:
    response = await client.post(
        "/api/v1/search/candidates",
        json={
            "filters": {
                "role": "Python Developer",
            },
            "limit": 5,
        },
    )

    assert response.status_code == 401
    assert "internal service token" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_search_candidates_employer_contract_shape(
    client: AsyncClient, fake_handlers: dict[str, object]
) -> None:
    response = await client.post(
        "/api/v1/search/candidates",
        headers={"Authorization": "Bearer super-secret-internal-token"},
        json={
            "filters": {
                "role": "Python Developer",
                "must_skills": [{"skill": "Python", "level": 5}],
                "location": "Paris",
            },
            "limit": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"total", "items"}
    assert isinstance(body["total"], int)
    assert isinstance(body["items"], list)
    assert body["items"], "items must not be empty in this contract scenario"

    item = body["items"][0]
    expected_keys = {
        "candidate_id",
        "display_name",
        "headline_role",
        "experience_years",
        "location",
        "skills",
        "salary_min",
        "salary_max",
        "currency",
        "english_level",
        "about_me",
        "match_score",
        "explanation",
    }
    assert expected_keys.issubset(item.keys())
    assert UUID(item["candidate_id"])
    assert isinstance(item["display_name"], str)
    assert isinstance(item["headline_role"], str)
    assert isinstance(item["experience_years"], float)
    assert item["location"] is None or isinstance(item["location"], str)
    assert isinstance(item["skills"], list)
    assert item["salary_min"] is None or isinstance(item["salary_min"], int)
    assert item["salary_max"] is None or isinstance(item["salary_max"], int)
    assert item["currency"] is None or isinstance(item["currency"], str)
    assert item["english_level"] is None or isinstance(item["english_level"], str)
    assert item["about_me"] is None or isinstance(item["about_me"], str)
    assert isinstance(item["match_score"], float)
    assert item["explanation"] is None or isinstance(item["explanation"], dict)


@pytest.mark.asyncio
async def test_internal_rebuild_requires_auth(
    client: AsyncClient, fake_handlers: dict[str, object]
) -> None:
    response = await client.post(
        "/api/v1/internal/index/rebuild",
        json={"batch_size": 10},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_internal_rebuild_with_auth(
    client: AsyncClient,
    fake_handlers: dict[str, object],
) -> None:
    response = await client.post(
        "/api/v1/internal/index/rebuild",
        headers={"Authorization": "Bearer super-secret-internal-token"},
        json={"batch_size": 10},
    )

    assert response.status_code == 200
    assert response.json() == {
        "processed": 2,
        "indexed": 2,
        "skipped": 0,
        "failed": 0,
    }


@pytest.mark.asyncio
async def test_internal_upsert_candidate_document(
    client: AsyncClient,
    fake_handlers: dict[str, object],
) -> None:
    candidate_id = uuid4()

    response = await client.post(
        f"/api/v1/internal/index/candidates/{candidate_id}",
        headers={"Authorization": "Bearer super-secret-internal-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_id"] == str(candidate_id)
    assert body["vector_present"] is True
    assert body["vector_store"] == "milvus"
    assert body["document"]["display_name"] == "Ivan"


@pytest.mark.asyncio
async def test_internal_delete_candidate_document(
    client: AsyncClient,
    fake_handlers: dict[str, object],
) -> None:
    candidate_id = uuid4()

    response = await client.delete(
        f"/api/v1/internal/index/candidates/{candidate_id}",
        headers={"Authorization": "Bearer super-secret-internal-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": True}


@pytest.mark.asyncio
async def test_internal_get_candidate_document(
    client: AsyncClient,
    fake_handlers: dict[str, object],
) -> None:
    candidate_id = uuid4()

    response = await client.get(
        f"/api/v1/internal/index/candidates/{candidate_id}",
        headers={"Authorization": "Bearer super-secret-internal-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_id"] == str(candidate_id)
    assert body["document"]["headline_role"] == "Python Developer"


@pytest.mark.asyncio
async def test_internal_get_candidate_document_not_found(
    app: FastAPI,
    client: AsyncClient,
    fake_handlers: dict[str, object],
) -> None:
    app.dependency_overrides[get_get_candidate_document_handler] = lambda: (
        FakeGetCandidateDocumentHandler(should_raise=True)
    )
    candidate_id = uuid4()

    response = await client.get(
        f"/api/v1/internal/index/candidates/{candidate_id}",
        headers={"Authorization": "Bearer super-secret-internal-token"},
    )

    assert response.status_code == 404
    body = response.json()
    assert "candidate document" in body["detail"]
    assert "request_id" in body
