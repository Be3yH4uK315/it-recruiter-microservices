import pytest
import pytest_asyncio
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.milvus_client import MilvusClientWrapper
from app.core.resources import ResourceManager

@pytest.fixture
def mock_es_client():
    """Мок для Elasticsearch."""
    es = AsyncMock()
    es.search = AsyncMock(return_value={"hits": {"hits": []}})
    es.mget = AsyncMock(return_value={"docs": []})
    es.index = AsyncMock()
    es.delete = AsyncMock()
    es.indices.create = AsyncMock()
    es.indices.put_alias = AsyncMock()
    es.indices.get_alias = AsyncMock(return_value={})
    return es

@pytest.fixture
def mock_milvus():
    """Мок для Milvus."""
    milvus = MagicMock(spec=MilvusClientWrapper)
    milvus.search = AsyncMock(return_value=[])
    milvus.insert = AsyncMock()
    milvus.delete = AsyncMock()
    return milvus

@pytest.fixture
def mock_ml_resources(mocker):
    """
    Мокаем загрузку тяжелых нейросетей.
    Вместо реальных векторов возвращаем заглушки.
    """
    mock_res = MagicMock(spec=ResourceManager)
    mock_embed = MagicMock()
    mock_embed.encode.return_value = np.array([0.1] * 768, dtype=np.float32)
    mock_res.embedding_model = mock_embed
    mock_ranker = MagicMock()
    mock_ranker.predict.return_value = np.array([2.5, -1.0]) 
    mock_res.ranker_model = mock_ranker
    mock_res.get_embedding_cached = MagicMock(return_value=np.array([0.1] * 768))
    
    return mock_res

@pytest.fixture(autouse=True)
def override_dependencies(mock_es_client, mock_milvus, mock_ml_resources, mocker):
    """
    Автоматическая подмена зависимостей во всем приложении перед каждым тестом.
    """
    mocker.patch("app.services.indexer.indexer.es_client", mock_es_client)
    mocker.patch("app.services.milvus_client.milvus_client", mock_milvus)
    mocker.patch("app.services.search_logic.milvus_client", mock_milvus)
    mocker.patch("app.services.indexer.milvus_client", mock_milvus)
    
    mocker.patch("app.core.resources_search.resources", mock_ml_resources)
    mocker.patch("app.services.search_logic.resources", mock_ml_resources)
    mocker.patch("app.services.ranker.resources", mock_ml_resources)
    mocker.patch("app.services.indexer.resources", mock_ml_resources)

@pytest_asyncio.fixture(scope="function")
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
