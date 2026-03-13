from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.schemas.file import FileTypeEnum
from fastapi import HTTPException, UploadFile


def create_mock_upload_file(filename: str, content_type: str, file_size: int = 100) -> UploadFile:
    mock_file = MagicMock(spec=UploadFile)

    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.size = file_size

    mock_file.read = AsyncMock(return_value=b"%PDF-1.4...")
    mock_file.seek = AsyncMock()

    mock_file.file = MagicMock()

    return mock_file


@pytest.mark.asyncio
async def test_upload_file_success(file_service, mock_file_repo, mock_s3_service, mocker):
    """Тест успешной загрузки (с обходом Magic Bytes)."""

    mock_guess = MagicMock()
    mock_guess.mime = "application/pdf"
    mock_guess.extension = "pdf"

    mocker.patch("app.services.file.filetype.guess", return_value=mock_guess)

    upload_file = create_mock_upload_file("test.pdf", "application/pdf")
    owner_id = 123

    result = await file_service.upload_file(upload_file, owner_id, FileTypeEnum.RESUME)

    mock_s3_service.upload_fileobj.assert_called_once()
    mock_file_repo.create.assert_called_once()

    assert result.filename == "test.pdf"
    assert result.owner_telegram_id == owner_id
    assert "resumes/123/" in result.s3_key


@pytest.mark.asyncio
async def test_upload_file_invalid_type(file_service, mocker):
    """Тест: защита Magic Bytes (пытаемся загрузить exe под видом картинки)."""

    mock_guess = MagicMock()
    mock_guess.mime = "application/x-msdownload"

    mocker.patch("app.services.file.filetype.guess", return_value=mock_guess)

    upload_file = create_mock_upload_file("virus.jpg", "image/jpeg")

    with pytest.raises(HTTPException) as exc:
        await file_service.upload_file(upload_file, 123, FileTypeEnum.AVATAR)

    assert exc.value.status_code == 415


@pytest.mark.asyncio
async def test_upload_s3_failure(file_service, mock_s3_service, mocker):
    """Тест: S3 упал -> 502."""

    mock_guess = MagicMock()
    mock_guess.mime = "application/pdf"

    mocker.patch("app.services.file.filetype.guess", return_value=mock_guess)

    mock_s3_service.upload_fileobj.side_effect = Exception("S3 Down")

    upload_file = create_mock_upload_file("test.pdf", "application/pdf")

    with pytest.raises(HTTPException) as exc:
        await file_service.upload_file(upload_file, 123, FileTypeEnum.RESUME)

    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_generate_upload_url(file_service, mock_s3_service):
    """Тест генерации Presigned URL для прямой загрузки."""

    mock_s3_service.generate_presigned_url.return_value = "https://s3.url"

    res = await file_service.generate_upload_url(
        owner_id="123",
        filename="test.pdf",
        content_type="application/pdf",
        file_type=FileTypeEnum.RESUME,
    )

    assert res["upload_url"] == "https://s3.url"
    assert "resumes/123/" in res["object_key"]

    mock_s3_service.generate_presigned_url.assert_called_once()


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
