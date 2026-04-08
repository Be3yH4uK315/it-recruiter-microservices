from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.application.auth.services.jwt_service import JwtService
from app.config import Settings
from app.domain.auth.entities import User
from app.domain.auth.enums import UserRole
from app.domain.auth.value_objects import TelegramProfile
from app.infrastructure.auth.jwt_bearer import (
    _extract_bearer_token,
    require_access_token_claims,
)


@pytest.fixture
def jwt_settings() -> Settings:
    return Settings(
        jwt_secret_key="unit-test-secret-at-least-32-characters",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
    )


@pytest.fixture
def user() -> User:
    from uuid import uuid4

    return User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(
            telegram_id=123456,
            username="dmitry",
        ),
        role=UserRole.EMPLOYER,
    )


def test_extract_bearer_token_returns_token() -> None:
    assert _extract_bearer_token("Bearer access-token") == "access-token"


def test_extract_bearer_token_returns_none_for_invalid_header() -> None:
    assert _extract_bearer_token("Basic access-token") is None


@pytest.mark.asyncio
async def test_require_access_token_claims_returns_claims(
    monkeypatch: pytest.MonkeyPatch,
    jwt_settings: Settings,
    user: User,
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", jwt_settings.jwt_secret_key)
    monkeypatch.setenv("JWT_ALGORITHM", jwt_settings.jwt_algorithm)
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")

    from app.config import get_settings

    get_settings.cache_clear()

    service = JwtService(get_settings())
    token, _ = service.create_access_token(user=user)

    claims = await require_access_token_claims(f"Bearer {token}")

    assert claims.subject == str(user.id)
    assert claims.telegram_id == user.telegram_profile.telegram_id
    assert claims.role == user.role


@pytest.mark.asyncio
async def test_require_access_token_claims_rejects_missing_header() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await require_access_token_claims(None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing access token. Use Authorization: Bearer <token>."


@pytest.mark.asyncio
async def test_require_access_token_claims_rejects_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-secret-at-least-32-characters")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")

    from app.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        await require_access_token_claims("Bearer invalid-token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid access token."
