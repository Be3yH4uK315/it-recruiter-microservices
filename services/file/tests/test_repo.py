from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.models.file import FileRecord
from app.repositories.file import FileRepository


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def repo(mock_session):
    return FileRepository(mock_session)


@pytest.mark.asyncio
async def test_repo_create(repo, mock_session):
    record = FileRecord(
        id=uuid4(),
        owner_telegram_id=123,
        filename="test.txt",
        content_type="text/plain",
        size_bytes=100,
        s3_key="key",
        bucket="b",
        file_type="resume",
    )

    res = await repo.create(record)

    assert res == record
    mock_session.add.assert_called_once_with(record)


@pytest.mark.asyncio
async def test_repo_get_by_id(repo, mock_session):
    fid = uuid4()

    mock_result = MagicMock()
    mock_scalars = MagicMock()

    record = FileRecord(id=fid)

    mock_scalars.first.return_value = record
    mock_result.scalars.return_value = mock_scalars

    mock_session.execute.return_value = mock_result

    res = await repo.get_by_id(fid)

    assert res == record
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_repo_delete(repo, mock_session):
    record = FileRecord(id=uuid4())

    await repo.delete(record)

    mock_session.delete.assert_called_once_with(record)
