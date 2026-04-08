from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.infrastructure.integrations.auth_gateway import HttpAuthGateway


@pytest.mark.asyncio
async def test_verify_access_token_uses_positive_cache() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "user_id": "11111111-1111-1111-1111-111111111111",
                "telegram_id": 123456,
                "role": "employer",
                "roles": ["employer"],
                "is_active": True,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        gateway = HttpAuthGateway(
            client=client,
            base_url="http://auth-api:8000",
            internal_token="test-token",
            cache_ttl_seconds=30,
            cache_max_entries=128,
        )

        first = await gateway.verify_access_token(access_token="access-token")
        second = await gateway.verify_access_token(access_token="access-token")

    assert first.user_id == second.user_id
    assert calls == 1


@pytest.mark.asyncio
async def test_verify_access_token_does_not_cache_expired_subject() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "user_id": "11111111-1111-1111-1111-111111111111",
                "telegram_id": 123456,
                "role": "employer",
                "roles": ["employer"],
                "is_active": True,
                "expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        gateway = HttpAuthGateway(
            client=client,
            base_url="http://auth-api:8000",
            internal_token="test-token",
            cache_ttl_seconds=30,
            cache_max_entries=128,
        )

        await gateway.verify_access_token(access_token="access-token")
        await gateway.verify_access_token(access_token="access-token")

    assert calls == 2
