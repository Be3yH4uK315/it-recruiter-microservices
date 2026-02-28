import pytest
import pytest_asyncio
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.schemas import employer as schemas
from app.api.v1.dependencies import get_service, get_current_user_tg_id

def create_valid_employer():
    return schemas.Employer(
        id=uuid4(),
        telegram_id=55555,
        company="Big Tech",
        contacts={"email": "hr@bigtech.com"}
    )

@pytest_asyncio.fixture(scope="function")
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_e2e_create_employer(async_client, mocker):
    """
    Сценарий: Регистрация работодателя.
    """
    mock_service = mocker.AsyncMock()
    valid_employer = create_valid_employer()
    mock_service.register_employer.return_value = valid_employer
    
    app.dependency_overrides[get_service] = lambda: mock_service
    app.dependency_overrides[get_current_user_tg_id] = lambda: 55555

    payload = {
        "telegram_id": 55555,
        "company": "Big Tech",
        "contacts": {"email": "hr@bigtech.com"}
    }
    
    response = await async_client.post("/v1/employers/", json=payload)
    
    assert response.status_code == 201
    assert response.json()["company"] == "Big Tech"
    
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_e2e_create_search_session(async_client, mocker):
    """
    Сценарий: Создание сессии поиска.
    """
    mock_service = mocker.AsyncMock()
    session_id = uuid4()
    
    mock_session = schemas.SearchSession(
        id=session_id,
        employer_id=uuid4(),
        title="Find Python Dev",
        status="active",
        filters={"role": "Python", "experience_min": 2}
    )
    mock_service.create_search_session.return_value = mock_session
    
    app.dependency_overrides[get_service] = lambda: mock_service
    
    payload = {
        "title": "Find Python Dev",
        "filters": {
            "role": "Python",
            "experience_min": 2,
            "must_skills": ["Django"]
        }
    }
    
    employer_id = uuid4()
    response = await async_client.post(f"/v1/employers/{employer_id}/searches", json=payload)
    
    assert response.status_code == 200
    assert response.json()["title"] == "Find Python Dev"
    
    app.dependency_overrides = {}

@pytest_asyncio.fixture(scope="function")
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_e2e_make_decision(async_client, mocker):
    """Сценарий: Лайк/Скип кандидата."""
    mock_service = mocker.AsyncMock()
    mock_service.submit_decision.return_value = schemas.Decision(
        id=uuid4(),
        session_id=uuid4(),
        candidate_id=uuid4(),
        decision="like",
        note="Good"
    )
    
    app.dependency_overrides[get_service] = lambda: mock_service
    
    payload = {
        "candidate_id": str(uuid4()),
        "decision": "like",
        "note": "Good"
    }
    
    resp = await async_client.post(f"/v1/employers/searches/{uuid4()}/decisions", json=payload)
    assert resp.status_code == 200
    assert resp.json()["decision"] == "like"
    
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_e2e_update_employer(async_client, mocker):
    """Сценарий: Обновление профиля компании."""
    mock_service = mocker.AsyncMock()
    mock_service.update_profile.return_value = schemas.Employer(
        id=uuid4(),
        telegram_id=123,
        company="Updated Corp",
        contacts={}
    )
    
    app.dependency_overrides[get_service] = lambda: mock_service
    
    payload = {"company": "Updated Corp"}
    resp = await async_client.patch(f"/v1/employers/{uuid4()}", json=payload)
    
    assert resp.status_code == 200
    assert resp.json()["company"] == "Updated Corp"
    
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_internal_access_check(async_client, mocker):
    """Сценарий: Проверка доступа (Internal)."""
    mock_service = mocker.AsyncMock()
    mock_service.check_access.return_value = True
    
    app.dependency_overrides[get_service] = lambda: mock_service
    
    params = {"candidate_id": str(uuid4()), "employer_telegram_id": 123}
    resp = await async_client.get("/v1/employers/internal/access-check", params=params)
    
    assert resp.status_code == 200
    assert resp.json()["granted"] is True
    
    mock_service.check_access.return_value = False
    resp = await async_client.get("/v1/employers/internal/access-check", params=params)
    assert resp.status_code == 403

    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_respond_to_contact_request(async_client, mocker):
    """Сценарий: Ответ на запрос контактов."""
    mock_service = mocker.AsyncMock()
    mock_service.respond_to_request.return_value = True
    
    app.dependency_overrides[get_service] = lambda: mock_service
    
    resp = await async_client.put(f"/v1/employers/contact-requests/{uuid4()}", json={"granted": True})
    assert resp.status_code == 200
    assert resp.json()["status"] == "updated"
    
    app.dependency_overrides = {}
