from datetime import datetime
from uuid import uuid4

import pytest
from app.api.v1.dependencies import get_current_user_tg_id, get_service
from app.schemas.file import FileResponse


@pytest.mark.asyncio
async def test_e2e_upload_file(async_client, mocker):
    """
    3.2.3. Сценарий: Загрузка файла через API.
    """
    mock_service = mocker.AsyncMock()
    file_id = uuid4()
    mock_response = FileResponse(
        id=file_id,
        filename="cv.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        created_at=datetime.now(),
    )
    mock_service.upload_file.return_value = mock_response

    from app.main import app

    app.dependency_overrides[get_service] = lambda: mock_service
    app.dependency_overrides[get_current_user_tg_id] = lambda: 555

    files = {"file": ("cv.pdf", b"%PDF...", "application/pdf")}
    data = {"file_type": "resume"}

    response = await async_client.post("/v1/files/upload", files=files, data=data)

    assert response.status_code == 201
    assert response.json()["id"] == str(file_id)

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_e2e_get_url(async_client, mocker):
    """Сценарий: Получение ссылки."""
    mock_service = mocker.AsyncMock()
    mock_service.get_download_url.return_value = "http://minio/bucket/file"

    from app.main import app

    app.dependency_overrides[get_service] = lambda: mock_service

    file_id = uuid4()
    response = await async_client.get(f"/v1/files/{file_id}/url")

    assert response.status_code == 200
    assert response.json()["download_url"] == "http://minio/bucket/file"

    app.dependency_overrides = {}
