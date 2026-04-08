from __future__ import annotations


async def test_healthcheck(client) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "auth-service"
    assert "components" in payload
