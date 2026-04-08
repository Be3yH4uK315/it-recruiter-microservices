from __future__ import annotations

import pytest

import app.worker as worker_module


@pytest.mark.asyncio
async def test_run_worker_calls_publisher_and_worker(monkeypatch) -> None:
    calls: list[str] = []

    class FakePublisher:
        def __init__(self, *, amqp_url: str, exchange_name: str) -> None:
            assert amqp_url
            assert exchange_name

        async def connect(self) -> None:
            calls.append("publisher.connect")

        async def close(self) -> None:
            calls.append("publisher.close")

    class FakeOutboxWorker:
        def __init__(
            self,
            *,
            session_factory,
            publisher,
            batch_size: int,
            poll_interval_seconds: float,
            max_retries: int,
        ) -> None:
            assert session_factory is not None
            assert publisher is not None
            assert batch_size > 0
            assert poll_interval_seconds > 0
            assert max_retries > 0

        async def run(self, *, stop_event) -> None:
            calls.append("worker.run")
            stop_event.set()

    class FakeEngine:
        async def dispose(self) -> None:
            calls.append("engine.dispose")

    class FakeSettings:
        rabbitmq_url = "amqp://guest:guest@localhost:5672/"
        rabbitmq_exchange = "candidate.events"
        outbox_batch_size = 100
        outbox_poll_interval_seconds = 0.01
        outbox_max_retries = 3
        log_level = "INFO"
        log_json = False

    monkeypatch.setattr(worker_module, "EventPublisher", FakePublisher)
    monkeypatch.setattr(worker_module, "OutboxWorker", FakeOutboxWorker)
    monkeypatch.setattr(worker_module, "engine", FakeEngine())
    monkeypatch.setattr(worker_module, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(worker_module, "configure_logging", lambda settings: None)

    await worker_module.run_worker()

    assert calls == [
        "publisher.connect",
        "worker.run",
        "publisher.close",
        "engine.dispose",
    ]
