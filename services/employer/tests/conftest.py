import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.employer import EmployerService
from app.repositories.employer import EmployerRepository
from app.core.resources import resources
import httpx

@pytest.fixture
def mock_db_session():
    """Фейковая сессия БД."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    return session

@pytest.fixture
def mock_employer_repo():
    """Фейковый репозиторий."""
    repo = MagicMock(spec=EmployerRepository)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_telegram_id = AsyncMock()
    repo.create_session = AsyncMock()
    repo.get_session = AsyncMock()
    repo.get_viewed_candidate_ids = AsyncMock(return_value=[])
    repo.create_decision = AsyncMock()
    return repo

@pytest.fixture
def employer_service(mock_db_session, mock_employer_repo):
    """Сервис с моками внутри."""
    service = EmployerService(mock_db_session)
    service.repo = mock_employer_repo
    return service

@pytest_asyncio.fixture
async def setup_resources():
    """Инициализация HTTP-клиента для тестов."""
    resources.http_client = httpx.AsyncClient(base_url="http://test")
    yield
    await resources.http_client.aclose()
    resources.http_client = None
