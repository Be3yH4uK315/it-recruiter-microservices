from __future__ import annotations

import httpx


async def test_bot_login_returns_token_pair_and_user(
    internal_client: httpx.AsyncClient,
    bot_login_payload: dict,
) -> None:
    response = await internal_client.post("/api/v1/auth/login/bot", json=bot_login_payload)

    assert response.status_code == 200

    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str) and payload["access_token"]
    assert isinstance(payload["refresh_token"], str) and payload["refresh_token"]

    user = payload["user"]
    assert user["telegram_id"] == bot_login_payload["telegram_id"]
    assert user["role"] == bot_login_payload["role"]
    assert user["username"] == bot_login_payload["username"]
    assert user["is_active"] is True


async def test_me_returns_current_user_profile(
    client: httpx.AsyncClient,
    bot_login,
) -> None:
    session = await bot_login()

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {session['access_token']}"},
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["telegram_id"] == 1001
    assert payload["role"] == "employer"
    assert payload["username"] == "acme_hr"
    assert payload["is_active"] is True
