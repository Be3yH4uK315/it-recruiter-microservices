from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from app.application.common.exceptions import IntegrationApplicationError
from app.infrastructure.integrations.candidate_gateway import HttpCandidateGateway


class FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "ok") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeHttpClient:
    def __init__(self, response: FakeResponse | None = None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.calls = []

    async def request(self, method: str, url: str, params=None, headers=None):
        self.calls.append((method, url, params, headers))
        if self.exc is not None:
            raise self.exc
        return self.response


def make_candidate_payload(candidate_id):
    return {
        "id": str(candidate_id),
        "telegram_id": 123,
        "display_name": "Ivan",
        "headline_role": "Python Developer",
        "location": "Paris",
        "work_modes": ["remote"],
        "contacts_visibility": "on_request",
        "status": "active",
        "english_level": "B2",
        "about_me": "Async backend",
        "salary_min": 100000,
        "salary_max": 150000,
        "currency": "RUB",
        "skills": [{"skill": "python", "level": 5, "kind": "hard"}],
        "education": [],
        "experiences": [],
        "projects": [],
        "avatar_file_id": None,
        "resume_file_id": None,
        "created_at": None,
        "updated_at": None,
        "version_id": 1,
    }


@pytest.mark.asyncio
async def test_get_candidate_profile_returns_payload() -> None:
    candidate_id = uuid4()
    client = FakeHttpClient(
        response=FakeResponse(
            200,
            payload=make_candidate_payload(candidate_id),
        )
    )
    gateway = HttpCandidateGateway(
        client=client,
        base_url="http://candidate-api:8000",
        internal_token="token",
    )

    result = await gateway.get_candidate_profile(candidate_id=candidate_id)

    assert result is not None
    assert result.id == candidate_id
    assert result.display_name == "Ivan"
    assert client.calls[0][0] == "GET"
    assert client.calls[0][3]["Authorization"] == "Bearer token"


@pytest.mark.asyncio
async def test_get_candidate_profile_returns_none_on_404() -> None:
    candidate_id = uuid4()
    client = FakeHttpClient(response=FakeResponse(404))
    gateway = HttpCandidateGateway(
        client=client,
        base_url="http://candidate-api:8000",
        internal_token=None,
    )

    result = await gateway.get_candidate_profile(candidate_id=candidate_id)

    assert result is None


@pytest.mark.asyncio
async def test_list_candidates_returns_items() -> None:
    candidate_id = uuid4()
    client = FakeHttpClient(
        response=FakeResponse(
            200,
            payload={"items": [make_candidate_payload(candidate_id)]},
        )
    )
    gateway = HttpCandidateGateway(
        client=client,
        base_url="http://candidate-api:8000",
        internal_token=None,
    )

    result = await gateway.list_candidates(limit=10, offset=0)

    assert len(result) == 1
    assert result[0].id == candidate_id


@pytest.mark.asyncio
async def test_gateway_raises_on_http_error() -> None:
    client = FakeHttpClient(exc=httpx.ConnectError("boom"))
    gateway = HttpCandidateGateway(
        client=client,
        base_url="http://candidate-api:8000",
        internal_token=None,
    )

    with pytest.raises(IntegrationApplicationError, match="candidate service request failed"):
        await gateway.list_candidates(limit=10, offset=0)


@pytest.mark.asyncio
async def test_gateway_raises_on_invalid_payload() -> None:
    client = FakeHttpClient(response=FakeResponse(200, payload={"bad": "shape"}))
    gateway = HttpCandidateGateway(
        client=client,
        base_url="http://candidate-api:8000",
        internal_token=None,
    )

    with pytest.raises(IntegrationApplicationError, match="invalid candidate items payload"):
        await gateway.list_candidates(limit=10, offset=0)
