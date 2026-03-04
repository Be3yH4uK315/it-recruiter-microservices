import httpx
import pytest
import respx
from unittest.mock import AsyncMock
from httpx import Response
from app.services.api_client import CandidateAPIClient
from app.core.config import settings

@pytest.mark.asyncio
async def test_get_candidate_success(mocker):
    client = CandidateAPIClient()
    url = f"{settings.CANDIDATE_SERVICE_URL}/candidates/by-telegram/123"
    
    async with respx.mock(base_url=None) as respx_mock:
        respx_mock.get(url).mock(return_value=Response(200, json={"id": "1"}))
        
        res = await client.get_candidate_by_telegram_id(123)
        assert res["id"] == "1"

@pytest.mark.asyncio
async def test_get_candidate_404(mocker):
    client = CandidateAPIClient()
    url = f"{settings.CANDIDATE_SERVICE_URL}/candidates/by-telegram/123"
    
    async with respx.mock(base_url=None) as respx_mock:
        respx_mock.get(url).mock(return_value=Response(404))
        
        res = await client.get_candidate_by_telegram_id(123)
        assert res is None

@pytest.mark.asyncio
async def test_register_candidate_retry(mocker):
    client = CandidateAPIClient()
    url = f"{settings.CANDIDATE_SERVICE_URL}/candidates/"
    
    fake_request = httpx.Request("POST", url)
    
    async with respx.mock(base_url=None) as respx_mock:
        route = respx_mock.post(url).mock(side_effect=[
            httpx.RequestError("Network Error", request=fake_request),
            Response(201, json={"id": "new"})
        ])
        
        res = await client.register_candidate_profile({"telegram_id": 123})
        
        assert res["id"] == "new"
        assert route.call_count == 2
