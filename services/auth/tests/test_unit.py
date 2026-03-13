import hashlib
import hmac
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.config import settings
from app.core.security import create_access_token, decode_token, verify_telegram_data
from app.models.auth import RefreshToken, User, UserRole
from fastapi import HTTPException


def generate_valid_telegram_hash(data: dict, token: str) -> str:
    data_check_arr = []

    for key, value in sorted(data.items()):
        if key != "hash" and value is not None:
            data_check_arr.append(f"{key}={value}")

    data_check_string = "\n".join(data_check_arr)
    secret_key = hashlib.sha256(token.encode()).digest()

    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def test_verify_telegram_data_valid():
    data = {
        "id": 12345,
        "first_name": "Test",
        "auth_date": int(time.time()),
        "username": "testuser",
    }

    data["hash"] = generate_valid_telegram_hash(data, settings.TELEGRAM_BOT_TOKEN)

    assert verify_telegram_data(data, settings.TELEGRAM_BOT_TOKEN) is True


def test_verify_telegram_data_expired():
    data = {
        "id": 12345,
        "auth_date": int(time.time()) - 87000,
        "hash": "fake",
    }

    assert verify_telegram_data(data, settings.TELEGRAM_BOT_TOKEN) is False


def test_jwt_generation_and_decoding():
    payload = {"sub": "user-uuid", "role": "admin"}

    token = create_access_token(payload)
    decoded = decode_token(token)

    assert decoded["sub"] == "user-uuid"
    assert decoded["role"] == "admin"
    assert "exp" in decoded


@pytest.mark.asyncio
async def test_auth_via_bot_new_user(auth_service, mock_db_session):
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
    assert args.role == UserRole.CANDIDATE


@pytest.mark.asyncio
async def test_auth_via_bot_existing_user(auth_service, mock_db_session):
    existing_user = User(
        id="uid",
        telegram_id=999,
        username="old_name",
        is_active=True,
        role=UserRole.CANDIDATE,
    )

    mock_result = MagicMock()
    mock_scalars = MagicMock()

    mock_result.scalars.return_value = mock_scalars
    mock_scalars.first.return_value = existing_user

    mock_db_session.execute.return_value = mock_result

    auth_service._issue_tokens_for_user = AsyncMock(return_value="tokens")

    await auth_service.authenticate_via_trusted_bot(telegram_id=999, username="new_name")

    assert existing_user.username == "new_name"


@pytest.mark.asyncio
async def test_auth_via_bot_blocked_user(auth_service, mock_db_session):
    blocked_user = User(id="uid", telegram_id=999, username="name", is_active=False)

    mock_result = MagicMock()
    mock_scalars = MagicMock()

    mock_result.scalars.return_value = mock_scalars
    mock_scalars.first.return_value = blocked_user

    mock_db_session.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc:
        await auth_service.authenticate_via_trusted_bot(telegram_id=999, username="name")

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_auth_via_bot_change_role(auth_service, mock_db_session):
    existing_user = User(
        id="uid",
        telegram_id=999,
        username="name",
        is_active=True,
        role=UserRole.CANDIDATE,
    )

    mock_result = MagicMock()
    mock_scalars = MagicMock()

    mock_result.scalars.return_value = mock_scalars
    mock_scalars.first.return_value = existing_user

    mock_db_session.execute.return_value = mock_result

    auth_service._issue_tokens_for_user = AsyncMock(return_value="tokens")

    await auth_service.authenticate_via_trusted_bot(
        telegram_id=999, username="name", role=UserRole.EMPLOYER
    )

    assert existing_user.role == UserRole.EMPLOYER


@pytest.mark.asyncio
async def test_refresh_token_success(auth_service, mock_db_session, mocker):
    mocker.patch(
        "app.core.security.decode_token",
        return_value={
            "type": "refresh",
            "sub": "uid",
            "exp": int(time.time()) + 3600,
        },
    )

    db_token = RefreshToken(user_id="uid", token_hash="hash", revoked=False)

    user = User(id="uid", telegram_id=123, is_active=True, role=UserRole.CANDIDATE)

    mock_scalars = MagicMock()
    mock_scalars.first.side_effect = [db_token, user]

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db_session.execute.return_value = mock_result

    auth_service._issue_tokens_for_user = AsyncMock(return_value="new_tokens")

    res = await auth_service.refresh_access_token("fake_token")

    assert res == "new_tokens"

    mock_db_session.delete.assert_called_with(db_token)


@pytest.mark.asyncio
async def test_refresh_token_revoked(auth_service, mock_db_session, mocker):
    mocker.patch(
        "app.core.security.decode_token",
        return_value={"type": "refresh", "sub": "uid"},
    )

    db_token = RefreshToken(user_id="uid", token_hash="hash", revoked=True)

    mock_scalars = MagicMock()
    mock_scalars.first.return_value = db_token

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db_session.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc:
        await auth_service.refresh_access_token("fake_token")

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_logout(auth_service, mock_db_session):
    await auth_service.logout("fake_token")

    mock_db_session.execute.assert_called()
    mock_db_session.commit.assert_called()


@pytest.mark.asyncio
async def test_logout_all(auth_service, mock_db_session, mocker):
    mocker.patch(
        "app.core.security.decode_token",
        return_value={"type": "refresh", "sub": "uid"},
    )

    await auth_service.logout_all("fake_token")

    mock_db_session.execute.assert_called()
    mock_db_session.commit.assert_called()
