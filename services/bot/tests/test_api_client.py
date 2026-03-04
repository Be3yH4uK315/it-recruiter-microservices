import pytest
from unittest.mock import AsyncMock
from httpx import Response, Request
from app.services.api_client import CandidateAPIClient, APIHTTPError

fake_request = Request("GET", "http://test")

@pytest.mark.asyncio
async def test_get_candidate_success(mocker):
    mock_response = Response(200, json={"id": "1"}, request=fake_request)
    mocker.patch("app.services.api_client.BaseClient._request", new_callable=AsyncMock, return_value=mock_response)
    
    client = CandidateAPIClient()
    res = await client.get_candidate_by_telegram_id(123)
    assert res["id"] == "1"

@pytest.mark.asyncio
async def test_get_candidate_404(mocker):
    mock_response = Response(404, request=fake_request)
    mocker.patch("app.services.api_client.BaseClient._request", new_callable=AsyncMock, return_value=mock_response)
    
    client = CandidateAPIClient()
    
    with pytest.raises(APIHTTPError) as exc_info:
        await client.get_candidate_by_telegram_id(123)
    
    assert exc_info.value.status_code == 404

@pytest.mark.asyncio
async def test_register_candidate_retry(mocker):
    mock_response = Response(201, json={"id": "new"}, request=fake_request)
    mocker.patch("app.services.api_client.BaseClient._request", new_callable=AsyncMock, return_value=mock_response)
    
    client = CandidateAPIClient()
    res = await client.register_candidate_profile({"telegram_id": 123})
    
    assert res["id"] == "new"
