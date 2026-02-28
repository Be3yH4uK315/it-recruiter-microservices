import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.publisher import RabbitMQProducer

@pytest.mark.asyncio
async def test_publisher_connect_success(mocker):
    """Тест подключения."""
    mock_pika = mocker.patch('app.services.publisher.aio_pika')
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_pika.connect_robust = AsyncMock(return_value=mock_connection)
    mock_connection.channel.return_value = mock_channel
    
    producer = RabbitMQProducer()
    await producer.connect()
    
    assert producer.connection is not None
    assert producer.channel is not None
    mock_channel.declare_exchange.assert_called()

@pytest.mark.asyncio
async def test_publish_message_reconnects(mocker):
    """Тест: если соединения нет, оно восстанавливается."""
    mock_pika = mocker.patch('app.services.publisher.aio_pika')
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    mock_pika.connect_robust = AsyncMock(return_value=mock_connection)
    mock_connection.channel.return_value = mock_channel
    mock_channel.declare_exchange.return_value = mock_exchange
    
    producer = RabbitMQProducer()
    
    await producer.publish_message("key", b"body")
    
    mock_pika.connect_robust.assert_called()
    mock_exchange.publish.assert_called_once()
