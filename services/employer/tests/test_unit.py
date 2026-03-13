from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.schemas import employer as schemas


@pytest.mark.asyncio
async def test_register_employer(employer_service, mock_employer_repo):
    """Тест регистрации работодателя."""
    payload = schemas.EmployerCreate(telegram_id=123, company="TechCorp")
    mock_employer_repo.get_by_telegram_id.return_value = None
    mock_employer_repo.create.return_value = MagicMock(id=uuid4(), telegram_id=123)

    result = await employer_service.register_employer(payload)

    assert result.telegram_id == 123
    mock_employer_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_get_next_candidate_success(employer_service, mock_employer_repo):
    """
    Тест: Получение следующего кандидата.
    """
    session_id = uuid4()
    mock_session = MagicMock()
    mock_session.filters = {"role": "Developer"}
    mock_employer_repo.get_session.return_value = mock_session
    mock_employer_repo.get_by_id.return_value = MagicMock(id=uuid4(), telegram_id=123)

    from app.core.resources import resources

    resources.http_client = AsyncMock()

    mock_search_resp = MagicMock()
    mock_search_resp.status_code = 200
    mock_search_resp.json.return_value = {
        "candidate": {"id": "123e4567-e89b-12d3-a456-426614174000", "match_score": 0.95}
    }

    mock_cand_resp = MagicMock()
    mock_cand_resp.status_code = 200
    mock_cand_resp.json.return_value = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "display_name": "John Doe",
        "headline_role": "Python Dev",
        "experience_years": 5.5,
        "skills": [],
    }

    async def side_effect_request(url, *args, **kwargs):
        if "search" in str(url):
            return mock_search_resp
        if "candidates" in str(url):
            return mock_cand_resp
        return MagicMock(status_code=404)

    resources.http_client.post.side_effect = side_effect_request
    resources.http_client.get.side_effect = side_effect_request

    response = await employer_service.get_next_candidate(session_id)

    assert response.candidate is not None
    assert response.candidate.display_name == "John Doe"
    assert response.candidate.experience_years == 5.5


@pytest.mark.asyncio
async def test_request_contact_public(employer_service, mock_employer_repo):
    """Тест: Если контакты публичны, отдаем их сразу."""
    from app.core.resources import resources

    resources.http_client = AsyncMock()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": str(uuid4()),
        "contacts_visibility": "public",
        "contacts": {"email": "public@test.com"},
    }
    resources.http_client.get.return_value = mock_resp

    mock_employer_repo.get_contact_request.return_value = None
    mock_employer_repo.get_by_id.return_value = MagicMock(
        id=uuid4(), telegram_id=123, company="Test Co"
    )
    mock_employer_repo.create_contact_request.return_value = MagicMock(id=uuid4(), granted=True)

    payload = schemas.ContactsRequestCreate(candidate_id=uuid4())
    result = await employer_service.request_contact(uuid4(), payload)

    assert result.granted is True
    assert result.contacts == {"email": "public@test.com"}


@pytest.mark.asyncio
async def test_get_favorites_success(employer_service, mock_employer_repo, mocker):
    """Тест списка избранных кандидатов с параллельным запросом."""

    emp_id = uuid4()

    mock_employer_repo.get_by_id.return_value = MagicMock(telegram_id=123)

    cand1, cand2 = uuid4(), uuid4()
    mock_employer_repo.get_favorites.return_value = [cand1, cand2]

    mock_cb = mocker.AsyncMock()

    mock_cb.call.side_effect = [{"id": str(cand1)}, {"id": str(cand2)}]

    mocker.patch("app.services.employer.employer_service_breaker", mock_cb)

    res = await employer_service.get_favorites(emp_id)

    assert len(res) == 2
    assert res[0]["id"] == str(cand1)

    assert mock_cb.call.call_count == 2


@pytest.mark.asyncio
async def test_get_employer_statistics(employer_service, mock_employer_repo):
    """Тест получения HR-аналитики."""

    emp_id = uuid4()

    mock_employer_repo.get_by_id.return_value = MagicMock()

    mock_employer_repo.get_statistics.return_value = {
        "total_viewed": 50,
        "total_liked": 5,
        "total_contact_requests": 2,
        "total_contacts_granted": 1,
    }

    res = await employer_service.get_employer_statistics(emp_id)

    assert res.total_viewed == 50
    assert res.total_liked == 5


@pytest.mark.asyncio
async def test_request_contact_hidden_triggers_notification(
    employer_service, mock_employer_repo, mocker
):
    """Тест: Если контакты on_request, создается заявка и инфа для бота."""

    emp_id = uuid4()
    cand_id = uuid4()

    mock_employer_repo.get_by_id.return_value = MagicMock(
        id=emp_id, telegram_id=123, company="Test Corp"
    )

    mock_employer_repo.get_contact_request.return_value = None

    req_id = uuid4()

    mock_employer_repo.create_contact_request.return_value = MagicMock(id=req_id, granted=False)

    mock_cb = mocker.AsyncMock()
    mock_cb.call.return_value = {"telegram_id": 999, "contacts_visibility": "on_request"}

    mocker.patch("app.services.employer.employer_service_breaker", mock_cb)

    payload = schemas.ContactsRequestCreate(candidate_id=cand_id)

    res = await employer_service.request_contact(emp_id, payload)

    assert type(res) is dict
    assert res["granted"] is False
    assert res["notification_info"]["candidate_telegram_id"] == 999
    assert res["notification_info"]["employer_company"] == "Test Corp"
