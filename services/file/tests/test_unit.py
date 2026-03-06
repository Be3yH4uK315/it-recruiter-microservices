from io import BytesIO
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile


@pytest.mark.asyncio
async def test_upload_file_success(file_service, mock_file_repo, mock_s3_service):
    """Тест успешной загрузки."""
    file_content = b"test content"
    upload_file = MagicMock(spec=UploadFile)
    upload_file.filename = "test.png"
    upload_file.file = BytesIO(file_content)
    upload_file.content_type = "image/png"
    upload_file.file.seek = MagicMock()
    upload_file.file.tell = MagicMock(return_value=len(file_content))

    owner_id = 123

    result = await file_service.upload_file(upload_file, owner_id, "avatar")

    mock_s3_service.upload_fileobj.assert_called_once()
    mock_file_repo.create.assert_called_once()

    assert result.filename == "test.png"
    assert result.owner_telegram_id == owner_id
    assert result.size_bytes == len(file_content)
    assert "avatars/123/" in result.s3_key


@pytest.mark.asyncio
async def test_upload_s3_failure(file_service, mock_s3_service):
    """Тест: S3 упал -> 502."""
    mock_s3_service.upload_fileobj.side_effect = Exception("S3 Down")

    upload_file = MagicMock(spec=UploadFile)
    upload_file.filename = "test.txt"
    upload_file.file = BytesIO(b"data")
    upload_file.content_type = "text/plain"

    with pytest.raises(HTTPException) as exc:
        await file_service.upload_file(upload_file, 123, "resume")

    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_delete_file_success(file_service, mock_file_repo, mock_s3_service):
    file_id = uuid4()
    mock_record = MagicMock()
    mock_record.owner_telegram_id = 123
    mock_record.s3_key = "key"

    mock_file_repo.get_by_id.return_value = mock_record

    await file_service.delete_file(file_id, 123)

    mock_s3_service.delete_file.assert_called_with("key")
    mock_file_repo.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_file_forbidden(file_service, mock_file_repo):
    mock_record = MagicMock()
    mock_record.owner_telegram_id = 999
    mock_file_repo.get_by_id.return_value = mock_record

    with pytest.raises(HTTPException) as exc:
        await file_service.delete_file(uuid4(), 123)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_download_url(file_service, mock_file_repo, mock_s3_service):
    mock_file_repo.get_by_id.return_value = MagicMock(s3_key="path/to/file")
    url = await file_service.get_download_url(uuid4())
    assert url == "https://s3.fake/url"
