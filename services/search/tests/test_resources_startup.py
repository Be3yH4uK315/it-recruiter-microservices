import pytest
from unittest.mock import AsyncMock
from app.core.resources import ResourceManager

@pytest.mark.asyncio
async def test_resources_lifecycle(mocker):
    """Тест startup/shutdown."""
    res = ResourceManager()
    mocker.patch("app.core.resources_search.SentenceTransformer")
    mocker.patch("app.core.resources_search.CrossEncoder")
    mock_client_cls = mocker.patch("app.core.resources_search.httpx.AsyncClient")
    mock_client_instance = AsyncMock()
    mock_client_cls.return_value = mock_client_instance
    await res.startup()
    assert res.embedding_model is not None
    assert res.http_client is not None
    await res.shutdown()
    mock_client_instance.aclose.assert_awaited_once()
