import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.services.file import FileService
from app.repositories.file import FileRepository
from app.services.s3_client import S3Service

@pytest.fixture
def mock_db_session():
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    return session

@pytest.fixture
def mock_file_repo():
    repo = MagicMock(spec=FileRepository)
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.delete = AsyncMock()
    return repo

@pytest.fixture
def mock_s3_service():
    """Мок для S3, чтобы не лезть в сеть."""
    s3 = MagicMock(spec=S3Service)
    s3.upload_fileobj = AsyncMock()
    s3.delete_file = AsyncMock()
    s3.generate_presigned_url = AsyncMock(return_value="https://s3.fake/url")
    s3.ensure_bucket_exists = AsyncMock()
    return s3

@pytest.fixture
def file_service(mock_db_session, mock_file_repo, mock_s3_service):
    """Сервис с внедренными моками."""
    with pytest.MonkeyPatch().context() as m:
        m.setattr("app.services.file.s3_service", mock_s3_service)
        service = FileService(mock_db_session)
        service.repo = mock_file_repo
        yield service

@pytest_asyncio.fixture(scope="function")
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
