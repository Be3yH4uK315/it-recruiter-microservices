import pytest
from unittest.mock import AsyncMock
from app.services.consumer import consumer
from app.services.indexer import indexer

@pytest.mark.asyncio
async def test_consumer_delete_event(mocker):
    """Тест события удаления."""
    message = mocker.Mock()
    message.routing_key = "candidate.deleted"
    message.body = b'{"id": "uid-del"}'
    message.process = mocker.MagicMock()
    
    mocker.patch.object(indexer, "delete_candidate", new_callable=AsyncMock)
    
    await consumer._process_message(message)
    indexer.delete_candidate.assert_called_with("uid-del")

@pytest.mark.asyncio
async def test_indexer_process_update_no_id(mocker):
    """Тест: пришло событие без ID -> игнор."""
    mocker.patch.object(indexer.es_client, "index", new_callable=AsyncMock)
    await indexer.process_candidate_update({"name": "No ID"})
    indexer.es_client.index.assert_not_called()

@pytest.mark.asyncio
async def test_indexer_delete_with_shadow(mocker):
    """Тест удаления из обоих индексов (если идет реиндекс)."""
    indexer._shadow_index_name = "shadow-1"
    mocker.patch.object(indexer.es_client, "delete", new_callable=AsyncMock)
    mocker.patch("app.services.indexer.milvus_client.delete", new_callable=AsyncMock)
    
    await indexer.delete_candidate("uid-1")
    
    assert indexer.es_client.delete.call_count == 2
    indexer._shadow_index_name = None
