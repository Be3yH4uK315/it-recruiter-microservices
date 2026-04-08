from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.application.common.exceptions import (
    IntegrationApplicationError,
    ValidationApplicationError,
)
from app.domain.search.errors import (
    CandidateDocumentNotFoundError,
    InvalidSearchFilterError,
    SearchBackendUnavailableError,
)
from app.infrastructure.web.exception_handlers import register_exception_handlers


@pytest.fixture()
def app() -> FastAPI:
    application = FastAPI()
    register_exception_handlers(application)

    @application.get("/validation")
    async def validation_route():
        raise ValidationApplicationError("bad request")

    @application.get("/integration")
    async def integration_route():
        raise IntegrationApplicationError("service down")

    @application.get("/invalid-filter")
    async def invalid_filter_route():
        raise InvalidSearchFilterError("bad filter")

    @application.get("/not-found")
    async def not_found_route():
        raise CandidateDocumentNotFoundError("missing candidate")

    @application.get("/backend")
    async def backend_route():
        raise SearchBackendUnavailableError("backend unavailable")

    @application.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = "req-123"
        return await call_next(request)

    return application


@pytest.fixture()
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_validation_exception_handler(client: AsyncClient) -> None:
    response = await client.get("/validation")
    assert response.status_code == 422
    assert response.json() == {"detail": "bad request", "request_id": "req-123"}


@pytest.mark.asyncio
async def test_integration_exception_handler(client: AsyncClient) -> None:
    response = await client.get("/integration")
    assert response.status_code == 503
    assert response.json() == {"detail": "service down", "request_id": "req-123"}


@pytest.mark.asyncio
async def test_invalid_filter_exception_handler(client: AsyncClient) -> None:
    response = await client.get("/invalid-filter")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_not_found_exception_handler(client: AsyncClient) -> None:
    response = await client.get("/not-found")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_backend_exception_handler(client: AsyncClient) -> None:
    response = await client.get("/backend")
    assert response.status_code == 503
