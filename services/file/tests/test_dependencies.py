import pytest
from app.api.v1.dependencies import get_current_user_tg_id
from app.core.config import settings
from fastapi import HTTPException
from jose import jwt


@pytest.mark.asyncio
async def test_get_current_user_valid_token():
    payload = {"tg_id": 12345}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    user_id = await get_current_user_tg_id(token)
    assert user_id == 12345


@pytest.mark.asyncio
async def test_get_current_user_invalid_token():
    with pytest.raises(HTTPException):
        await get_current_user_tg_id("invalid.token")


@pytest.mark.asyncio
async def test_get_current_user_missing_tg_id():
    payload = {"sub": "user"}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    with pytest.raises(HTTPException):
        await get_current_user_tg_id(token)
