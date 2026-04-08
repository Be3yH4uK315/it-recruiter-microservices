from __future__ import annotations

import asyncio

import pytest


class StubPublisher:
    def __init__(self, *, amqp_url: str, exchange_name: str) -> None:
        self.amqp_url = amqp_url
        self.exchange_name = exchange_name
        self.connected = False
        self.closed = False

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.closed = True


class StubWorker:
    def __init__(
        self,
        *,
        session_factory,
        publisher,
        batch_size: int,
        poll_interval_seconds: float,
        max_retries: int,
    ) -> None:
        self.session_factory = session_factory
        self.publisher = publisher
        self.batch_size = batch_size
        self.poll_interval_seconds = poll_interval_seconds
        self.max_retries = max_retries
        self.run_called = False

    async def run(self, *, stop_event: asyncio.Event) -> None:
        self.run_called = True
        stop_event.set()


@pytest.mark.asyncio
async def test_run_worker_wires_publisher_and_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.worker as worker_module
    from app.config import get_settings

    monkeypatch.setenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
    monkeypatch.setenv("RABBITMQ_EXCHANGE", "auth.events")
    monkeypatch.setenv("OUTBOX_BATCH_SIZE", "50")
    monkeypatch.setenv("OUTBOX_POLL_INTERVAL_SECONDS", "0.5")
    monkeypatch.setenv("OUTBOX_MAX_RETRIES", "7")
    get_settings.cache_clear()

    created: dict[str, object] = {}

    def publisher_factory(*, amqp_url: str, exchange_name: str) -> StubPublisher:
        publisher = StubPublisher(amqp_url=amqp_url, exchange_name=exchange_name)
        created["publisher"] = publisher
        return publisher

    def worker_factory(
        *,
        session_factory,
        publisher,
        batch_size: int,
        poll_interval_seconds: float,
        max_retries: int,
    ) -> StubWorker:
        worker = StubWorker(
            session_factory=session_factory,
            publisher=publisher,
            batch_size=batch_size,
            poll_interval_seconds=poll_interval_seconds,
            max_retries=max_retries,
        )
        created["worker"] = worker
        return worker

    monkeypatch.setattr(worker_module, "EventPublisher", publisher_factory)
    monkeypatch.setattr(worker_module, "OutboxWorker", worker_factory)
    monkeypatch.setattr(worker_module, "configure_logging", lambda *_: None)

    class StubEngine:
        disposed = False

        @staticmethod
        async def dispose() -> None:
            StubEngine.disposed = True

    monkeypatch.setattr(worker_module, "engine", StubEngine)

    await worker_module.run_worker()

    publisher = created["publisher"]
    worker = created["worker"]

    assert isinstance(publisher, StubPublisher)
    assert isinstance(worker, StubWorker)
    assert publisher.connected is True
    assert publisher.closed is True
    assert worker.run_called is True
    assert worker.publisher is publisher
    assert worker.batch_size == 50
    assert worker.poll_interval_seconds == 0.5
    assert worker.max_retries == 7
    assert StubEngine.disposed is True


def test_worker_main_calls_asyncio_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.worker as worker_module

    called: dict[str, object] = {}

    def fake_asyncio_run(coro) -> None:
        called["is_coroutine"] = asyncio.iscoroutine(coro)
        coro.close()

    monkeypatch.setattr(worker_module.asyncio, "run", fake_asyncio_run)

    worker_module.main()

    assert called["is_coroutine"] is True
