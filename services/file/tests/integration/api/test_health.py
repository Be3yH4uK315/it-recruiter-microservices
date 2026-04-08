from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client) -> None:
    response = await client.get("/health")

    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "file-service"
    assert payload["components"]["storage"]["status"] == "ok"


@pytest.mark.asyncio
async def test_s3_health_returns_up(client) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["components"]["storage"]["status"] == "ok"
