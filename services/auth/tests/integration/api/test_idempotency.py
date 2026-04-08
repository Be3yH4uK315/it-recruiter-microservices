from __future__ import annotations

import httpx


async def test_idempotency_returns_same_response_for_same_key_and_payload(
    internal_client: httpx.AsyncClient,
    bot_login_payload: dict,
) -> None:
    headers = {"Idempotency-Key": "same-key-1"}

    first = await internal_client.post(
        "/api/v1/auth/login/bot",
        json=bot_login_payload,
        headers=headers,
    )
    second = await internal_client.post(
        "/api/v1/auth/login/bot",
        json=bot_login_payload,
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert second.headers["Idempotency-Key"] == "same-key-1"


async def test_idempotency_rejects_same_key_with_different_payload(
    internal_client: httpx.AsyncClient,
    bot_login_payload: dict,
) -> None:
    headers = {"Idempotency-Key": "same-key-2"}

    first = await internal_client.post(
        "/api/v1/auth/login/bot",
        json=bot_login_payload,
        headers=headers,
    )
    assert first.status_code == 200

    changed_payload = {
        **bot_login_payload,
        "first_name": "Changed",
    }

    second = await internal_client.post(
        "/api/v1/auth/login/bot",
        json=changed_payload,
        headers=headers,
    )

    assert second.status_code == 409
    assert second.json()["detail"] == "Idempotency key reuse with different payload"
