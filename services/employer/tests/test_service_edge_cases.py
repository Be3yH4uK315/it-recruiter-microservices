from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_get_next_candidate_search_unavailable(employer_service, mock_employer_repo):
    """Тест: Search Service недоступен (503)."""
    from app.core.resources import resources
    from httpx import RequestError

    mock_employer_repo.get_session.return_value = MagicMock(filters={})
    resources.http_client = AsyncMock()
    resources.http_client.post.side_effect = RequestError("Down")

    with pytest.raises(HTTPException) as exc:
        await employer_service.get_next_candidate(uuid4())

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_get_next_candidate_invalid_criteria(employer_service, mock_employer_repo):
    """Тест: Search Service вернул 422 (Невалидные фильтры)."""
    from app.core.resources import resources

    mock_employer_repo.get_session.return_value = MagicMock(filters={})
    resources.http_client = AsyncMock()

    resp = MagicMock()
    resp.status_code = 422
    resp.text = "Bad filters"
    resources.http_client.post.return_value = resp

    result = await employer_service.get_next_candidate(uuid4())
    assert result.message == "Invalid search criteria"


@pytest.mark.asyncio
async def test_check_access_logic(employer_service, mock_employer_repo):
    """Тест логики проверки доступа."""
    mock_employer_repo.get_by_telegram_id.return_value = None
    assert await employer_service.check_access(123, uuid4()) is False

    mock_employer_repo.get_by_telegram_id.return_value = MagicMock(id=uuid4())
    mock_employer_repo.get_contact_request.return_value = None
    assert await employer_service.check_access(123, uuid4()) is False

    mock_employer_repo.get_contact_request.return_value = MagicMock(granted=False)
    assert await employer_service.check_access(123, uuid4()) is False

    mock_employer_repo.get_contact_request.return_value = MagicMock(granted=True)
    assert await employer_service.check_access(123, uuid4()) is True
