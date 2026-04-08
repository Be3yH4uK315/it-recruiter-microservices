from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import app.worker as worker_module


@pytest.mark.asyncio
async def test_run_worker_connects_runs_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        rabbitmq_exchange="app.events",
        outbox_batch_size=100,
        outbox_poll_interval_seconds=1.0,
        outbox_max_retries=10,
    )

    configure_logging_mock = Mock()
    logger = Mock()

    publisher_instance = Mock()
    publisher_instance.connect = AsyncMock()
    publisher_instance.close = AsyncMock()

    worker_instance = Mock()
    worker_instance.run = AsyncMock()

    fake_engine = SimpleNamespace(dispose=AsyncMock())

    class FakeEvent:
        def __init__(self) -> None:
            self._set = True

        def is_set(self) -> bool:
            return True

        def set(self) -> None:
            return None

    monkeypatch.setattr(worker_module, "get_settings", lambda: settings)
    monkeypatch.setattr(worker_module, "configure_logging", configure_logging_mock)
    monkeypatch.setattr(worker_module, "get_logger", lambda name: logger)
    monkeypatch.setattr(worker_module, "EventPublisher", lambda **kwargs: publisher_instance)
    monkeypatch.setattr(worker_module, "OutboxWorker", lambda **kwargs: worker_instance)
    monkeypatch.setattr(worker_module.asyncio, "Event", FakeEvent)
    monkeypatch.setattr(worker_module, "engine", fake_engine)

    await worker_module.run_worker()

    publisher_instance.connect.assert_awaited_once()
    worker_instance.run.assert_awaited_once()
    publisher_instance.close.assert_awaited_once()
    fake_engine.dispose.assert_awaited_once()
