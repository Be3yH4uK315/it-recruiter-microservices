from unittest.mock import AsyncMock

import pytest
from app.services.s3_client import S3Service
from botocore.exceptions import ClientError


@pytest.mark.asyncio
async def test_ensure_bucket_exists_creates_if_missing(mocker):
    """
    Тест: Если бакета нет (404), он создается.
    """
    s3 = S3Service()
    mock_client = AsyncMock()
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__.return_value = mock_client

    mocker.patch.object(s3.session, "client", return_value=mock_client_ctx)

    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    mock_client.head_bucket.side_effect = ClientError(error_response, "HeadBucket")

    await s3.ensure_bucket_exists()

    mock_client.create_bucket.assert_called_once_with(Bucket=s3.bucket)


@pytest.mark.asyncio
async def test_ensure_bucket_exists_ok(mocker):
    """Тест: Бакет есть, ничего делать не надо."""
    s3 = S3Service()
    mock_client = AsyncMock()
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__.return_value = mock_client
    mocker.patch.object(s3.session, "client", return_value=mock_client_ctx)

    await s3.ensure_bucket_exists()

    mock_client.create_bucket.assert_not_called()
