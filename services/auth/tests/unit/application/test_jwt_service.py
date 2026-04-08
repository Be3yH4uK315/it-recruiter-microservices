from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.application.auth.services.jwt_service import JwtService
from app.config import Settings
from app.domain.auth.entities import User
from app.domain.auth.enums import UserRole
from app.domain.auth.errors import InvalidAccessTokenError, InvalidRefreshTokenError
from app.domain.auth.value_objects import TelegramProfile


@pytest.fixture
def jwt_settings() -> Settings:
    return Settings(
        jwt_secret_key="unit-test-secret-at-least-32-characters",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def jwt_service(jwt_settings: Settings) -> JwtService:
    return JwtService(jwt_settings)


@pytest.fixture
def user() -> User:
    return User.register(
        id=uuid4(),
        telegram_profile=TelegramProfile(
            telegram_id=123456,
            username="dmitry",
            first_name="Dmitry",
            last_name="Test",
            photo_url="https://example.com/avatar.jpg",
        ),
        role=UserRole.EMPLOYER,
    )


def test_create_and_decode_access_token(
    jwt_service: JwtService,
    user: User,
) -> None:
    token, expires_at = jwt_service.create_access_token(user=user)

    assert isinstance(token, str)
    assert token
    assert expires_at.tzinfo is not None

    claims = jwt_service.decode_access_token(token)

    assert claims.subject == str(user.id)
    assert claims.telegram_id == user.telegram_profile.telegram_id
    assert claims.role == user.role
    assert claims.expires_at.tzinfo is not None


def test_create_and_decode_refresh_token(jwt_service: JwtService) -> None:
    session_id = str(uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    token = jwt_service.create_refresh_token(
        session_id=session_id,
        expires_at=expires_at,
    )

    claims = jwt_service.decode_refresh_token(token)

    assert claims.subject == session_id
    assert claims.expires_at.tzinfo is not None


def test_access_tokens_are_unique_even_for_same_user(
    jwt_service: JwtService,
    user: User,
) -> None:
    token_one, _ = jwt_service.create_access_token(user=user)
    token_two, _ = jwt_service.create_access_token(user=user)

    assert token_one != token_two


def test_decode_access_token_rejects_refresh_token(jwt_service: JwtService) -> None:
    session_id = str(uuid4())
    refresh_token = jwt_service.create_refresh_token(
        session_id=session_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )

    with pytest.raises(InvalidAccessTokenError, match="invalid token type"):
        jwt_service.decode_access_token(refresh_token)


def test_decode_refresh_token_rejects_access_token(
    jwt_service: JwtService,
    user: User,
) -> None:
    access_token, _ = jwt_service.create_access_token(user=user)

    with pytest.raises(InvalidRefreshTokenError, match="invalid token type"):
        jwt_service.decode_refresh_token(access_token)


def test_decode_invalid_token_raises(jwt_service: JwtService) -> None:
    with pytest.raises(InvalidRefreshTokenError, match="invalid token"):
        jwt_service.decode_refresh_token("not-a-jwt-token")


def test_access_token_ttl_seconds(jwt_service: JwtService) -> None:
    assert jwt_service.access_token_ttl_seconds == 3600


def test_refresh_token_ttl_seconds(jwt_service: JwtService) -> None:
    assert jwt_service.refresh_token_ttl_seconds == 7 * 24 * 60 * 60


def test_build_access_expires_at_is_in_future(jwt_service: JwtService) -> None:
    expires_at = jwt_service.build_access_expires_at()

    assert expires_at > datetime.now(timezone.utc)


def test_build_refresh_expires_at_is_in_future(jwt_service: JwtService) -> None:
    expires_at = jwt_service.build_refresh_expires_at()

    assert expires_at > datetime.now(timezone.utc)
