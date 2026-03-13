import time

import pytest
from app.core.config import settings
from app.main import app
from app.schemas.auth import TokenResponse
from app.services.service import AuthService


@pytest.mark.asyncio
async def test_login_bot_success(async_client, mocker):
    mock_service = mocker.AsyncMock(spec=AuthService)

    mock_service.authenticate_via_trusted_bot.return_value = TokenResponse(
        access_token="acc",
        refresh_token="ref",
        expires_in=3600,
    )

    from app.api.v1.endpoints.auth import get_auth_service

    app.dependency_overrides[get_auth_service] = lambda: mock_service

    payload = {
        "telegram_id": 123,
        "bot_secret": settings.INTERNAL_BOT_SECRET,
        "role": "candidate",
    }

    response = await async_client.post("/v1/auth/login/bot", json=payload)

    assert response.status_code == 200
    assert response.json()["access_token"] == "acc"

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_login_bot_wrong_secret(async_client):
    payload = {
        "telegram_id": 123,
        "bot_secret": "wrong-secret",
    }

    response = await async_client.post("/v1/auth/login/bot", json=payload)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_login_telegram_success(async_client, mocker):
    mock_service = mocker.AsyncMock(spec=AuthService)

    mock_service.authenticate_telegram.return_value = TokenResponse(
        access_token="acc2",
        refresh_token="ref2",
        expires_in=3600,
    )

    from app.api.v1.endpoints.auth import get_auth_service

    app.dependency_overrides[get_auth_service] = lambda: mock_service

    payload = {
        "id": 123,
        "first_name": "Ivan",
        "auth_date": int(time.time()),
        "hash": "somehash",
        "role": "employer",
    }

    response = await async_client.post("/v1/auth/login/telegram", json=payload)

    assert response.status_code == 200
    assert response.json()["access_token"] == "acc2"

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_refresh_token(async_client, mocker):
    mock_service = mocker.AsyncMock(spec=AuthService)

    mock_service.refresh_access_token.return_value = TokenResponse(
        access_token="new_acc",
        refresh_token="new_ref",
        expires_in=3600,
    )

    from app.api.v1.endpoints.auth import get_auth_service

    app.dependency_overrides[get_auth_service] = lambda: mock_service

    response = await async_client.post("/v1/auth/refresh", json={"refresh_token": "old_ref"})

    assert response.status_code == 200
    assert response.json()["access_token"] == "new_acc"

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_logout(async_client, mocker):
    mock_service = mocker.AsyncMock(spec=AuthService)

    mock_service.logout.return_value = None

    from app.api.v1.endpoints.auth import get_auth_service

    app.dependency_overrides[get_auth_service] = lambda: mock_service

    response = await async_client.post("/v1/auth/logout", json={"refresh_token": "token"})

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_logout_all(async_client, mocker):
    mock_service = mocker.AsyncMock(spec=AuthService)

    mock_service.logout_all.return_value = None

    from app.api.v1.endpoints.auth import get_auth_service

    app.dependency_overrides[get_auth_service] = lambda: mock_service

    response = await async_client.post("/v1/auth/logout/all", json={"refresh_token": "token"})

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    app.dependency_overrides = {}
