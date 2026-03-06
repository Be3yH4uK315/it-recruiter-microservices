import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.config import settings
from app.core.security import create_access_token, decode_token, verify_telegram_data
from app.models.auth import User


def generate_valid_telegram_hash(data: dict, token: str) -> str:
    """Вспомогательная функция для генерации валидного хеша в тестах."""
    data_check_arr = []
    for key, value in sorted(data.items()):
        if key != "hash" and value is not None:
            data_check_arr.append(f"{key}={value}")
    data_check_string = "\n".join(data_check_arr)
    secret_key = hashlib.sha256(token.encode()).digest()
    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def test_verify_telegram_data_valid():
    """Тест успешной проверки данных от Telegram."""
    data = {
        "id": 12345,
        "first_name": "Test",
        "auth_date": int(time.time()),
        "username": "testuser",
    }
    data["hash"] = generate_valid_telegram_hash(data, settings.TELEGRAM_BOT_TOKEN)

    assert verify_telegram_data(data, settings.TELEGRAM_BOT_TOKEN) is True


def test_verify_telegram_data_expired():
    """Тест: данные просрочены (более 24 часов)."""
    data = {"id": 12345, "auth_date": int(time.time()) - 87000, "hash": "fake"}
    assert verify_telegram_data(data, settings.TELEGRAM_BOT_TOKEN) is False


def test_verify_telegram_data_fake_hash():
    """Тест: поддельный хеш."""
    data = {"id": 12345, "auth_date": int(time.time()), "hash": "invalid_hash_value"}
    assert verify_telegram_data(data, settings.TELEGRAM_BOT_TOKEN) is False


def test_jwt_generation_and_decoding():
    """Тест создания и чтения JWT."""
    payload = {"sub": "user-uuid", "role": "admin"}
    token = create_access_token(payload)

    decoded = decode_token(token)
    assert decoded["sub"] == "user-uuid"
    assert decoded["role"] == "admin"
    assert "exp" in decoded


@pytest.mark.asyncio
async def test_auth_via_bot_new_user(auth_service, mock_db_session):
    """Тест: Новый пользователь заходит через бота."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_scalars.first.return_value = None

    mock_db_session.execute.return_value = mock_result

    auth_service._issue_tokens_for_user = AsyncMock(return_value="tokens")

    await auth_service.authenticate_via_trusted_bot(telegram_id=999, username="newbie")

    mock_db_session.add.assert_called()
    args = mock_db_session.add.call_args[0][0]
    assert isinstance(args, User)
    assert args.telegram_id == 999


@pytest.mark.asyncio
async def test_auth_via_bot_existing_user(auth_service, mock_db_session):
    """Тест: Существующий пользователь."""
    existing_user = User(id="uid", telegram_id=999, username="old_name")

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_scalars.first.return_value = existing_user

    mock_db_session.execute.return_value = mock_result

    auth_service._issue_tokens_for_user = AsyncMock(return_value="tokens")

    await auth_service.authenticate_via_trusted_bot(telegram_id=999, username="new_name")

    mock_db_session.add.assert_not_called()
    assert existing_user.username == "new_name"
