from __future__ import annotations

import httpx
import pytest
from asgi_lifespan import LifespanManager  # type: ignore

from app.main import create_app


@pytest.mark.asyncio
async def test_internal_auth_is_required() -> None:
    app = create_app()

    async with LifespanManager(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/v1/candidates/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 401
