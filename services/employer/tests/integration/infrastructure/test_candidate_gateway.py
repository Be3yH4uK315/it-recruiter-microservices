from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

import app.infrastructure.integrations.candidate_gateway as candidate_gateway_module
from app.infrastructure.integrations.candidate_gateway import HttpCandidateGateway
from app.infrastructure.integrations.circuit_breaker import (
    CircuitBreakerOpenError,
    candidate_gateway_circuit_breaker,
)


@pytest.fixture(autouse=True)
def reset_candidate_breaker() -> None:
    candidate_gateway_circuit_breaker._reset()


@pytest.mark.asyncio
async def test_candidate_gateway_returns_profile_on_200() -> None:
    candidate_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/v1/candidates/{candidate_id}/employer-view"
        assert request.headers["Authorization"] == "Bearer secret"
        assert request.url.params["employer_telegram_id"] == "1001"
        return httpx.Response(
            status_code=200,
            json={
                "id": str(candidate_id),
                "display_name": "Дмитрий Иванов",
                "headline_role": "Python Developer",
                "location": "Paris",
                "work_modes": ["remote", "hybrid"],
                "experience_years": 4.5,
                "skills": [{"skill": "python", "kind": "hard", "level": 5}],
                "salary_min": 250000,
                "salary_max": 350000,
                "currency": "RUB",
                "english_level": "B2",
                "contacts_visibility": "on_request",
                "contacts": {"email": "dmitry@example.com"},
                "avatar_file_id": None,
                "resume_file_id": None,
                "about_me": "Backend engineer",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://candidate") as client:
        gateway = HttpCandidateGateway(
            client=client,
            base_url="http://candidate",
            internal_token="secret",
        )

        result = await gateway.get_candidate_profile(
            candidate_id=candidate_id,
            employer_telegram_id=1001,
        )

    assert result is not None
    assert result.id == candidate_id
    assert result.display_name == "Дмитрий Иванов"
    assert result.match_score == 0.0


@pytest.mark.asyncio
async def test_candidate_gateway_returns_none_on_404() -> None:
    candidate_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://candidate") as client:
        gateway = HttpCandidateGateway(
            client=client,
            base_url="http://candidate",
            internal_token="secret",
        )

        result = await gateway.get_candidate_profile(
            candidate_id=candidate_id,
            employer_telegram_id=1001,
        )

    assert result is None


@pytest.mark.asyncio
async def test_candidate_gateway_returns_none_on_http_error() -> None:
    candidate_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://candidate") as client:
        gateway = HttpCandidateGateway(
            client=client,
            base_url="http://candidate",
            internal_token="secret",
        )

        result = await gateway.get_candidate_profile(
            candidate_id=candidate_id,
            employer_telegram_id=1001,
        )

    assert result is None


@pytest.mark.asyncio
async def test_candidate_gateway_returns_none_when_breaker_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_id = uuid4()

    class OpenBreaker:
        async def call(self, func):
            raise CircuitBreakerOpenError("open")

    monkeypatch.setattr(
        candidate_gateway_module,
        "candidate_gateway_circuit_breaker",
        OpenBreaker(),
    )

    async with httpx.AsyncClient(base_url="http://candidate") as client:
        gateway = HttpCandidateGateway(
            client=client,
            base_url="http://candidate",
            internal_token="secret",
        )

        result = await gateway.get_candidate_profile(
            candidate_id=candidate_id,
            employer_telegram_id=1001,
        )

    assert result is None
