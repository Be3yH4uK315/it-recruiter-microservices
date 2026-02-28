import pytest
import respx
from httpx import Response
from app.services.consumer import consumer
from app.services.indexer import indexer
from app.core.config import settings

@pytest.mark.asyncio
async def test_consumer_process_message_update(mocker, mock_es_client, mock_milvus):
    """
    Тест обработки события обновления кандидата.
    Должен обновить и ES, и Milvus.
    """
    message = mocker.Mock()
    message.routing_key = "candidate.updated.profile"
    message.body = b'{"payload": {"id": "uuid-1", "role": "Dev"}}'
    message.process = mocker.MagicMock()

    await consumer._process_message(message)
    
    mock_es_client.index.assert_called_once()
    call_args = mock_es_client.index.call_args[1]
    assert call_args["id"] == "uuid-1"
    
    mock_milvus.insert.assert_called_once()

@pytest.mark.asyncio
async def test_full_reindex_flow(mock_es_client, mock_milvus):
    """
    Тест полной переиндексации:
    1. Создание shadow-индекса.
    2. Скачивание данных из Candidate Service.
    3. Заливка в ES и Milvus.
    4. Переключение алиасов.
    """
    async with respx.mock(base_url=settings.CANDIDATE_SERVICE_URL) as respx_mock:
        respx_mock.get("/candidates/").mock(
            side_effect=[
                Response(200, json={"data": [{"id": "c1", "headline_role": "QA"}]}),
                Response(200, json={"data": []})
            ]
        )
        
        await indexer.run_full_reindex()
        mock_es_client.indices.create.assert_called()
        mock_es_client.index.assert_called()
        assert mock_es_client.index.call_args[1]["id"] == "c1"
        mock_milvus.insert.assert_called()
        mock_es_client.indices.update_aliases.assert_called()
