from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

import pytest

from app.application.auth.services.telegram_auth_service import TelegramAuthService
from app.config import Settings
from app.domain.auth.errors import InvalidTelegramAuthError


def build_telegram_payload(
    *,
    bot_token: str,
    user_id: str = "123456",
    first_name: str = "Dmitry",
    last_name: str = "Ivanov",
    username: str = "kostdmitry",
    photo_url: str = "https://example.com/avatar.jpg",
    auth_date: str | None = None,
) -> dict[str, str]:
    auth_date = auth_date or str(int(datetime.now(timezone.utc).timestamp()))

    payload = {
        "id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "photo_url": photo_url,
        "auth_date": auth_date,
    }

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(payload.items()) if value is not None
    )

    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    payload["hash"] = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return payload


@pytest.fixture
def telegram_settings() -> Settings:
    return Settings(
        telegram_bot_token="telegram-test-bot-token",
        telegram_auth_max_age_seconds=86400,
    )


@pytest.fixture
def telegram_auth_service(telegram_settings: Settings) -> TelegramAuthService:
    return TelegramAuthService(telegram_settings)


def test_validate_auth_payload_returns_telegram_profile(
    telegram_auth_service: TelegramAuthService,
    telegram_settings: Settings,
) -> None:
    payload = build_telegram_payload(bot_token=telegram_settings.telegram_bot_token)

    profile = telegram_auth_service.validate_auth_payload(payload)

    assert profile.telegram_id == 123456
    assert profile.first_name == "Dmitry"
    assert profile.last_name == "Ivanov"
    assert profile.username == "kostdmitry"
    assert profile.photo_url == "https://example.com/avatar.jpg"


def test_validate_auth_payload_raises_when_hash_missing(
    telegram_auth_service: TelegramAuthService,
    telegram_settings: Settings,
) -> None:
    payload = build_telegram_payload(bot_token=telegram_settings.telegram_bot_token)
    payload.pop("hash")

    with pytest.raises(InvalidTelegramAuthError, match="missing telegram auth hash"):
        telegram_auth_service.validate_auth_payload(payload)


def test_validate_auth_payload_raises_when_auth_date_missing(
    telegram_auth_service: TelegramAuthService,
    telegram_settings: Settings,
) -> None:
    payload = build_telegram_payload(bot_token=telegram_settings.telegram_bot_token)
    payload.pop("auth_date")

    with pytest.raises(InvalidTelegramAuthError, match="missing telegram auth date"):
        telegram_auth_service.validate_auth_payload(payload)


def test_validate_auth_payload_raises_when_user_id_missing(
    telegram_auth_service: TelegramAuthService,
    telegram_settings: Settings,
) -> None:
    payload = build_telegram_payload(bot_token=telegram_settings.telegram_bot_token)
    payload.pop("id")

    with pytest.raises(InvalidTelegramAuthError, match="missing telegram user id"):
        telegram_auth_service.validate_auth_payload(payload)


def test_validate_auth_payload_raises_when_auth_date_invalid(
    telegram_auth_service: TelegramAuthService,
    telegram_settings: Settings,
) -> None:
    payload = build_telegram_payload(
        bot_token=telegram_settings.telegram_bot_token,
        auth_date="not-a-number",
    )

    with pytest.raises(InvalidTelegramAuthError, match="invalid telegram auth date"):
        telegram_auth_service.validate_auth_payload(payload)


def test_validate_auth_payload_raises_when_user_id_invalid(
    telegram_auth_service: TelegramAuthService,
    telegram_settings: Settings,
) -> None:
    payload = build_telegram_payload(
        bot_token=telegram_settings.telegram_bot_token,
        user_id="abc",
    )

    with pytest.raises(InvalidTelegramAuthError, match="invalid telegram user id"):
        telegram_auth_service.validate_auth_payload(payload)


def test_validate_auth_payload_raises_when_payload_expired(
    telegram_auth_service: TelegramAuthService,
    telegram_settings: Settings,
) -> None:
    expired_auth_date = str(
        int(datetime.now(timezone.utc).timestamp())
        - telegram_settings.telegram_auth_max_age_seconds
        - 1
    )
    payload = build_telegram_payload(
        bot_token=telegram_settings.telegram_bot_token,
        auth_date=expired_auth_date,
    )

    with pytest.raises(InvalidTelegramAuthError, match="telegram auth payload is expired"):
        telegram_auth_service.validate_auth_payload(payload)


def test_validate_auth_payload_raises_when_hash_mismatch(
    telegram_auth_service: TelegramAuthService,
    telegram_settings: Settings,
) -> None:
    payload = build_telegram_payload(bot_token=telegram_settings.telegram_bot_token)
    payload["hash"] = "bad-hash-value"

    with pytest.raises(InvalidTelegramAuthError, match="telegram auth hash mismatch"):
        telegram_auth_service.validate_auth_payload(payload)
