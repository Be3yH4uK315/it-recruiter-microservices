import pytest
from app.core.config import settings
from app.main import app
from app.schemas.auth import TokenResponse
from app.services.service import AuthService


@pytest.mark.asyncio
async def test_login_bot_success(async_client, mocker):
    """E2E: Успешный вход через бота (Internal)."""
    mock_service = mocker.AsyncMock(spec=AuthService)
    mock_service.authenticate_via_trusted_bot.return_value = TokenResponse(
        access_token="acc", refresh_token="ref", expires_in=3600
    )
    from app.api.v1.endpoints.auth import get_auth_service

    app.dependency_overrides[get_auth_service] = lambda: mock_service

    payload = {"telegram_id": 123, "bot_secret": settings.INTERNAL_BOT_SECRET}

    response = await async_client.post("/v1/auth/login/bot", json=payload)

    assert response.status_code == 200
    assert response.json()["access_token"] == "acc"

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_login_bot_wrong_secret(async_client):
    """E2E: Неверный секрет бота -> 403."""
    payload = {"telegram_id": 123, "bot_secret": "wrong-secret"}
    response = await async_client.post("/v1/auth/login/bot", json=payload)
    assert response.status_code == 403
