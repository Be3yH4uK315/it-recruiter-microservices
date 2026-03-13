from unittest.mock import AsyncMock, MagicMock

import pytest
from app.services.outbox_worker import OutboxWorker
from app.services.publisher import publisher


@pytest.fixture
def mock_db_session():
    pass


@pytest.mark.asyncio
async def test_process_batch_success(mocker):
    """Тест обработки пачки сообщений."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    mocker.patch("app.services.outbox_worker.AsyncSessionLocal", return_value=mock_session)

    mock_repo = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = "msg1"
    mock_msg.routing_key = "test.event"
    mock_msg.message_body = {"foo": "bar"}
    mock_repo.get_pending_with_lock = AsyncMock(return_value=[mock_msg])
    mock_repo.mark_as_sent = AsyncMock()

    mocker.patch("app.services.outbox_worker.OutboxRepository", return_value=mock_repo)

    mocker.patch.object(publisher, "connect", AsyncMock())
    mocker.patch.object(publisher, "publish_message", AsyncMock())

    worker = OutboxWorker()

    processed = await worker.process_batch()

    assert processed == 1
    publisher.publish_message.assert_called_once()
    mock_repo.mark_as_sent.assert_called_once_with("msg1")
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_process_batch_with_error_and_dlq(mocker):
    """Тест: ошибка публикации -> ретрай -> DLQ."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mocker.patch("app.services.outbox_worker.AsyncSessionLocal", return_value=mock_session)

    mock_repo = MagicMock()
    mock_msg = MagicMock()
    mock_msg.id = "msg_fail"
    mock_msg.routing_key = "test.fail"
    mock_msg.message_body = {}
    mock_msg.retry_count = 5

    mock_repo.get_pending_with_lock = AsyncMock(return_value=[mock_msg])
    mocker.patch("app.services.outbox_worker.OutboxRepository", return_value=mock_repo)

    mock_pub = MagicMock()
    mock_pub.connect = AsyncMock()
    mock_pub.publish_message = AsyncMock(side_effect=Exception("Rabbit Down"))
    mock_pub.publish_dlq = AsyncMock()
    mocker.patch("app.services.outbox_worker.publisher", mock_pub)

    worker = OutboxWorker()
    await worker.process_batch()

    mock_pub.publish_message.assert_called()
    mock_pub.publish_dlq.assert_called_once()
    assert mock_msg.status == "failed"
