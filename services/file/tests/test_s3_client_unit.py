import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.s3_client import S3Service

@pytest.mark.asyncio
async def test_s3_generate_presigned_url(mocker):
    """Тест генерации URL."""
    s3 = S3Service()
    
    mock_client = AsyncMock()
    mock_client.generate_presigned_url.return_value = "http://minio:9000/bucket/key"
    
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client
    mocker.patch.object(s3.session, "client", return_value=mock_ctx)
    
    url = await s3.generate_presigned_url("key")
    
    assert "ngrok" in url or "minio" in url
    mock_client.generate_presigned_url.assert_called_once()

@pytest.mark.asyncio
async def test_s3_upload_fileobj(mocker):
    """Тест загрузки потока."""
    s3 = S3Service()
    mock_client = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client
    mocker.patch.object(s3.session, "client", return_value=mock_ctx)
    
    file_obj = MagicMock()
    await s3.upload_fileobj(file_obj, "key", "text/plain")
    
    mock_client.upload_fileobj.assert_called_once()

@pytest.mark.asyncio
async def test_s3_delete_file(mocker):
    """Тест удаления."""
    s3 = S3Service()
    mock_client = AsyncMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_client
    mocker.patch.object(s3.session, "client", return_value=mock_ctx)
    
    await s3.delete_file("key")
    mock_client.delete_object.assert_called_once()
