import pytest
import respx
import httpx
from httpx import Response
from uuid import uuid4
import pytest_asyncio

from app.core.config import settings
from app.core.circuit_breaker import CircuitBreakerOpenException, employer_service_breaker
from app.services.candidate import CandidateService
from app.core.resources import resources

@pytest_asyncio.fixture
async def setup_resources():
    """Инициализируем глобальный HTTP-клиент для тестов."""
    resources.http_client = httpx.AsyncClient(base_url="http://test")
    yield
    await resources.http_client.aclose()
    resources.http_client = None

@pytest.fixture
def integration_service(mock_db_session, mock_candidate_repo, mock_outbox_repo):
    """
    Чистый сервис без мока внутренней логики (_check_employer_access),
    в отличие от фикстуры в conftest.py.
    """
    service = CandidateService(mock_db_session)
    service.repo = mock_candidate_repo
    service.outbox = mock_outbox_repo
    return service

@pytest.mark.asyncio
async def test_check_employer_access_granted(integration_service, setup_resources):
    """
    Тест взаимодействия с Employer Service.
    """
    candidate_id = uuid4()
    employer_id = 999
    
    async with respx.mock(base_url=settings.EMPLOYER_SERVICE_URL) as respx_mock:
        route = respx_mock.get("/internal/access-check").mock(
            return_value=Response(200, json={"granted": True})
        )
        
        has_access = await integration_service._check_employer_access(candidate_id, employer_id)
        
        assert has_access is True
        assert route.called

@pytest.mark.asyncio
async def test_check_employer_access_forbidden(integration_service, setup_resources):
    """
    Тест отказа в доступе.
    """
    async with respx.mock(base_url=settings.EMPLOYER_SERVICE_URL) as respx_mock:
        respx_mock.get("/internal/access-check").mock(
            return_value=Response(403, json={"detail": "Forbidden"})
        )
        
        has_access = await integration_service._check_employer_access(uuid4(), 999)
        assert has_access is False

@pytest.mark.asyncio
async def test_get_resume_upload_url_integration(integration_service, mock_candidate_repo, setup_resources):
    """
    Тест взаимодействия с File Service.
    """
    tg_id = 123
    from app.models.candidate import Candidate
    mock_candidate_repo.get_by_telegram_id.return_value = Candidate(id=uuid4(), telegram_id=tg_id)

    expected_url = "https://s3.bucket/upload"
    
    async with respx.mock(base_url=settings.FILE_SERVICE_URL) as respx_mock:
        respx_mock.post("/files/resume/upload-url").mock(
            return_value=Response(200, json={
                "upload_url": expected_url,
                "object_key": "some_key",
                "expires_in": 3600
            })
        )
        
        result = await integration_service.get_resume_upload_url(tg_id, "cv.pdf", "application/pdf")
        
        assert result.upload_url == expected_url

@pytest.mark.asyncio
async def test_circuit_breaker_activates(integration_service, setup_resources):
    """
    Тест Circuit Breaker.
    """
    employer_service_breaker.failure_count = 0
    employer_service_breaker.state = "CLOSED"
    employer_service_breaker.last_failure_time = 0

    async with respx.mock(base_url=settings.EMPLOYER_SERVICE_URL) as respx_mock:
        respx_mock.get("/internal/access-check").mock(
            return_value=Response(500)
        )
        for _ in range(5):
            await integration_service._check_employer_access(uuid4(), 1)
            
        assert employer_service_breaker.state == "OPEN"

        with pytest.raises(CircuitBreakerOpenException):
             await employer_service_breaker.call(lambda: None)
