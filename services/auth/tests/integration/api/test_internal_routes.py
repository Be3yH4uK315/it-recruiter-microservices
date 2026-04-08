from __future__ import annotations

import httpx


async def test_internal_get_user_by_id(
    internal_client: httpx.AsyncClient,
    bot_login,
) -> None:
    session = await bot_login()
    user_id = session["user"]["id"]

    response = await internal_client.get(f"/api/v1/internal/auth/user/{user_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == user_id
    assert payload["telegram_id"] == 1001
    assert payload["role"] == "employer"
    assert payload["is_active"] is True


async def test_internal_get_user_by_telegram_id(
    internal_client: httpx.AsyncClient,
    bot_login,
) -> None:
    await bot_login()

    response = await internal_client.get("/api/v1/internal/auth/by-telegram/1001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["telegram_id"] == 1001
    assert payload["role"] == "employer"
    assert payload["is_active"] is True


async def test_bot_login_requires_internal_auth(
    client: httpx.AsyncClient,
    bot_login_payload: dict,
) -> None:
    response = await client.post("/api/v1/auth/login/bot", json=bot_login_payload)

    assert response.status_code == 401
    assert (
        response.json()["detail"]
        == "Missing internal service token. Use Authorization: Bearer <token>."
    )
