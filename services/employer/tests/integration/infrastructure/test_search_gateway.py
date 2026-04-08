from __future__ import annotations

from uuid import UUID

import httpx
import pytest

import app.infrastructure.integrations.search_gateway as search_gateway_module
from app.infrastructure.integrations.circuit_breaker import (
    CircuitBreakerOpenError,
    search_gateway_circuit_breaker,
)
from app.infrastructure.integrations.search_gateway import HttpSearchGateway


@pytest.fixture(autouse=True)
def reset_search_breaker() -> None:
    search_gateway_circuit_breaker._reset()


@pytest.mark.asyncio
async def test_search_gateway_returns_batch_on_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/search/candidates"
        assert request.headers["Authorization"] == "Bearer secret"
        assert request.method == "POST"
        assert request.read() == b'{"filters":{"role":"Python Developer"},"limit":50}'
        return httpx.Response(
            status_code=200,
            json={
                "total": 2,
                "items": [
                    {
                        "candidate_id": "00000000-0000-0000-0000-000000000001",
                        "display_name": "Alice",
                        "headline_role": "Python Developer",
                        "experience_years": 4.5,
                        "location": "Paris",
                        "skills": [{"skill": "python", "level": 5}],
                        "salary_min": 250000,
                        "salary_max": 350000,
                        "currency": "RUB",
                        "english_level": "B2",
                        "about_me": "Backend engineer",
                        "match_score": 0.92,
                        "explanation": {"rrf": 0.91},
                    },
                    {
                        "candidate_id": "00000000-0000-0000-0000-000000000002",
                        "display_name": "Bob",
                        "headline_role": "Backend Engineer",
                        "experience_years": 5.0,
                        "location": "Berlin",
                        "skills": [{"skill": "fastapi", "level": 4}],
                        "salary_min": 270000,
                        "salary_max": 370000,
                        "currency": "RUB",
                        "english_level": "B2",
                        "about_me": "Distributed systems",
                        "match_score": 0.88,
                        "explanation": {"rrf": 0.84},
                    },
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://search") as client:
        gateway = HttpSearchGateway(
            client=client,
            base_url="http://search",
            internal_token="secret",
        )

        result = await gateway.search_candidates(
            filters={"role": "Python Developer"},
            limit=50,
        )

    assert result.total == 2
    assert len(result.items) == 2
    assert result.items[0].candidate_id == UUID("00000000-0000-0000-0000-000000000001")
    assert result.items[0].display_name == "Alice"
    assert result.items[1].display_name == "Bob"


@pytest.mark.asyncio
async def test_search_gateway_returns_empty_batch_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://search") as client:
        gateway = HttpSearchGateway(
            client=client,
            base_url="http://search",
            internal_token="secret",
        )

        result = await gateway.search_candidates(
            filters={"role": "Python Developer"},
            limit=50,
        )

    assert result.total == 0
    assert result.items == []
    assert result.is_degraded is True


@pytest.mark.asyncio
async def test_search_gateway_returns_empty_batch_on_unauthorized_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=401,
            json={"detail": "Invalid internal service token."},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://search") as client:
        gateway = HttpSearchGateway(
            client=client,
            base_url="http://search",
            internal_token="wrong-token",
        )

        result = await gateway.search_candidates(
            filters={"role": "Python Developer"},
            limit=50,
        )

    assert result.total == 0
    assert result.items == []
    assert result.is_degraded is True


@pytest.mark.asyncio
async def test_search_gateway_returns_empty_batch_on_invalid_payload_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "total": 1,
                "items": {
                    "candidate_id": "00000000-0000-0000-0000-000000000001",
                },
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://search") as client:
        gateway = HttpSearchGateway(
            client=client,
            base_url="http://search",
            internal_token="secret",
        )

        result = await gateway.search_candidates(
            filters={"role": "Python Developer"},
            limit=50,
        )

    assert result.total == 0
    assert result.items == []
    assert result.is_degraded is True


@pytest.mark.asyncio
async def test_search_gateway_returns_empty_batch_when_breaker_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OpenBreaker:
        async def call(self, func):
            raise CircuitBreakerOpenError("open")

    monkeypatch.setattr(
        search_gateway_module,
        "search_gateway_circuit_breaker",
        OpenBreaker(),
    )

    async with httpx.AsyncClient(base_url="http://search") as client:
        gateway = HttpSearchGateway(
            client=client,
            base_url="http://search",
            internal_token="secret",
        )

        result = await gateway.search_candidates(
            filters={"role": "Python Developer"},
            limit=50,
        )

    assert result.total == 0
    assert result.items == []
    assert result.is_degraded is True
