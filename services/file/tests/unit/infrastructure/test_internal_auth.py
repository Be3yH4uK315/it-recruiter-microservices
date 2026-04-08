from __future__ import annotations

from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.infrastructure.auth.internal import require_internal_service


@pytest_asyncio.fixture
async def auth_app() -> AsyncIterator[FastAPI]:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_internal_service)])
    async def protected() -> dict:
        return {"status": "ok"}

    yield app


@pytest.mark.asyncio
async def test_require_internal_service_accepts_valid_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
    auth_app: FastAPI,
) -> None:
    import app.infrastructure.auth.internal as internal_auth

    class StubSettings:
        internal_service_token = "test-internal-token"

    monkeypatch.setattr(internal_auth, "get_settings", lambda: StubSettings())

    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": "Bearer test-internal-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_require_internal_service_rejects_missing_authorization_header(
    monkeypatch: pytest.MonkeyPatch,
    auth_app: FastAPI,
) -> None:
    import app.infrastructure.auth.internal as internal_auth

    class StubSettings:
        internal_service_token = "test-internal-token"

    monkeypatch.setattr(internal_auth, "get_settings", lambda: StubSettings())

    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/protected")

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Missing internal service token. Use Authorization: Bearer <token>."
    )


@pytest.mark.asyncio
async def test_require_internal_service_rejects_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
    auth_app: FastAPI,
) -> None:
    import app.infrastructure.auth.internal as internal_auth

    class StubSettings:
        internal_service_token = "test-internal-token"

    monkeypatch.setattr(internal_auth, "get_settings", lambda: StubSettings())

    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid internal service token."


@pytest.mark.asyncio
async def test_require_internal_service_returns_503_when_token_not_configured(
    monkeypatch: pytest.MonkeyPatch,
    auth_app: FastAPI,
) -> None:
    import app.infrastructure.auth.internal as internal_auth

    class StubSettings:
        internal_service_token = None

    monkeypatch.setattr(internal_auth, "get_settings", lambda: StubSettings())

    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": "Bearer anything"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Internal service authentication is not configured."
