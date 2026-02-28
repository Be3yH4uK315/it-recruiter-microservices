import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.schemas import candidate as schemas

from app.api.v1.dependencies import (
    get_candidate_service, 
    get_current_user_tg_id, 
    verify_candidate_ownership
)

def create_valid_candidate_response():
    """
    Создает реальный Pydantic-объект для валидации.
    """
    return schemas.Candidate(
        id=uuid4(),
        telegram_id=12345,
        display_name="E2E Tester",
        headline_role="Python Dev",
        location="Earth",
        work_modes=["remote"],
        contacts={"email": "test@test.com"},
        contacts_visibility="public",
        status="active",
        salary_min=100000,
        salary_max=200000,
        currency="RUB",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        skills=[],
        projects=[],
        experiences=[],
        education=[],
        avatars=[],
        resumes=[]
    )

@pytest_asyncio.fixture(scope="function")
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_e2e_create_and_get_candidate(async_client, mocker):
    """
    Сценарий: Создание кандидата и получение профиля.
    """
    mock_service = mocker.AsyncMock()
    valid_response = create_valid_candidate_response()
    
    mock_service.create_candidate.return_value = valid_response
    mock_service.get_candidate_by_telegram.return_value = valid_response

    app.dependency_overrides[get_candidate_service] = lambda: mock_service
    app.dependency_overrides[get_current_user_tg_id] = lambda: 12345

    payload = {
        "telegram_id": 12345,
        "display_name": "E2E Tester",
        "headline_role": "Python Dev",
        "contacts": {"email": "test@test.com"},
        "work_modes": ["remote"]
    }

    response = await async_client.post("/v1/candidates/", json=payload)
    assert response.status_code == 201, f"Error: {response.text}"
    assert response.json()["display_name"] == "E2E Tester"

    response_get = await async_client.get("/v1/candidates/by-telegram/12345")
    assert response_get.status_code == 200, f"Error: {response_get.text}"

    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_e2e_update_profile_flow(async_client, mocker):
    """
    Сценарий: Обновление профиля.
    """
    mock_service = mocker.AsyncMock()
    
    valid_response = create_valid_candidate_response()
    valid_response.skills = [
        schemas.CandidateSkill(
            id=uuid4(),
            candidate_id=valid_response.id,
            skill="fastapi",
            kind="hard",
            level=5
        )
    ]
    mock_service.update_candidate.return_value = valid_response
    mock_service.get_candidate_by_telegram.return_value = valid_response

    app.dependency_overrides[get_candidate_service] = lambda: mock_service
    app.dependency_overrides[verify_candidate_ownership] = lambda: None

    payload = {
        "skills": [{"skill": "FastAPI", "kind": "hard", "level": 5}]
    }

    response = await async_client.patch("/v1/candidates/by-telegram/12345", json=payload)
    
    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()
    assert len(data["skills"]) == 1
    assert data["skills"][0]["skill"] == "fastapi"

    app.dependency_overrides = {}
