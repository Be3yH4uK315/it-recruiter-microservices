from unittest.mock import AsyncMock, MagicMock

import pytest
from app.repositories.candidate import CandidateRepository
from app.repositories.outbox import OutboxRepository
from app.services.candidate import CandidateService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_db_session():
    """Фейковая сессия БД."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.expunge = MagicMock()
    return session


@pytest.fixture
def mock_candidate_repo():
    """Фейковый репозиторий кандидатов."""
    return AsyncMock(spec=CandidateRepository)


@pytest.fixture
def mock_outbox_repo():
    """Фейковый репозиторий Outbox."""
    repo = MagicMock(spec=OutboxRepository)
    repo.create = MagicMock()
    return repo


@pytest.fixture
def candidate_service(mock_db_session, mock_candidate_repo, mock_outbox_repo):
    """
    Инициализация сервиса с подмененными зависимостями.
    """
    service = CandidateService(mock_db_session)
    service.repo = mock_candidate_repo
    service.outbox = mock_outbox_repo
    service._check_employer_access = AsyncMock(return_value=True)

    return service
