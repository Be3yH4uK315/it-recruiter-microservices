from __future__ import annotations

import httpx


async def test_refresh_rotates_refresh_token(
    client: httpx.AsyncClient,
    bot_login,
) -> None:
    session = await bot_login()
    old_refresh_token = session["refresh_token"]

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert refresh_response.status_code == 200, refresh_response.text
    refreshed = refresh_response.json()

    assert refreshed["refresh_token"] != old_refresh_token
    assert refreshed["access_token"] != session["access_token"]
    assert refreshed["user"]["telegram_id"] == session["user"]["telegram_id"]

    second_refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )

    assert second_refresh_response.status_code == 401
    assert "detail" in second_refresh_response.json()


async def test_logout_revokes_refresh_token(
    client: httpx.AsyncClient,
    bot_login,
) -> None:
    session = await bot_login()
    refresh_token = session["refresh_token"]

    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_response.status_code == 204

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 401
    assert "detail" in refresh_response.json()


async def test_logout_all_revokes_all_user_sessions(
    client: httpx.AsyncClient,
    bot_login,
) -> None:
    session_one = await bot_login()
    session_two = await bot_login()

    logout_all_response = await client.post(
        "/api/v1/auth/logout/all",
        headers={"Authorization": f"Bearer {session_two['access_token']}"},
    )
    assert logout_all_response.status_code == 204

    refresh_one = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": session_one["refresh_token"]},
    )
    refresh_two = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": session_two["refresh_token"]},
    )

    assert refresh_one.status_code == 401
    assert refresh_two.status_code == 401
