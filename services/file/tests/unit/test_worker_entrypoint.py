from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import app.worker as worker_module


def test_main_calls_asyncio_run(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"value": False}

    def fake_run(coro):
        called["value"] = True
        coro.close()

    monkeypatch.setattr(worker_module.asyncio, "run", fake_run)
    worker_module.main()

    assert called["value"] is True


@pytest.mark.asyncio
async def test_stale_pending_cleanup_loop_runs_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    stop_event = asyncio.Event()
    called = {"value": 0}

    class Handler:
        async def __call__(self, command):
            called["value"] += 1
            assert command.reason == "pending_upload_expired"
            stop_event.set()

    await worker_module._run_stale_pending_cleanup_loop(
        stop_event=stop_event,
        handler_factory=lambda: Handler(),
        older_than_seconds=60,
        batch_size=10,
        poll_interval_seconds=0.01,
    )

    assert called["value"] == 1


@pytest.mark.asyncio
async def test_run_worker_starts_and_stops_components(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {
        "bucket": False,
        "publisher_connect": False,
        "publisher_close": False,
        "consumer_close": False,
        "engine_dispose": False,
        "outbox_run": False,
        "consumer_run": False,
    }
    stop_event_ref: dict[str, asyncio.Event] = {}

    settings = SimpleNamespace(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        rabbitmq_exchange="file.events",
        outbox_batch_size=10,
        outbox_poll_interval_seconds=0.01,
        outbox_max_retries=3,
        rabbitmq_cleanup_queue="file.cleanup.requested.queue",
        rabbitmq_cleanup_routing_key="file.cleanup.requested",
        pending_upload_ttl_seconds=60,
        pending_cleanup_batch_size=10,
        pending_cleanup_poll_interval_seconds=0.01,
    )

    class DummyStorage:
        def __init__(self, _settings):
            pass

        async def ensure_bucket_exists(self):
            state["bucket"] = True

    class DummyPublisher:
        def __init__(self, *, amqp_url: str, exchange_name: str):
            _ = (amqp_url, exchange_name)

        async def connect(self):
            state["publisher_connect"] = True

        async def close(self):
            state["publisher_close"] = True

    class DummyOutboxWorker:
        def __init__(self, **kwargs):
            _ = kwargs

        async def run(self, *, stop_event: asyncio.Event):
            state["outbox_run"] = True
            await stop_event.wait()

    class DummyConsumer:
        def __init__(self, **kwargs):
            _ = kwargs

        async def run(self, *, stop_event: asyncio.Event):
            state["consumer_run"] = True
            stop_event_ref["value"] = stop_event
            stop_event.set()

        async def close(self):
            state["consumer_close"] = True

    async def fake_dispose():
        state["engine_dispose"] = True

    class DummyLoop:
        def add_signal_handler(self, _sig, _handler):
            return None

    monkeypatch.setattr(worker_module, "get_settings", lambda: settings)
    monkeypatch.setattr(worker_module, "configure_logging", lambda _s: None)
    monkeypatch.setattr(worker_module, "S3ObjectStorage", DummyStorage)
    monkeypatch.setattr(worker_module, "EventPublisher", DummyPublisher)
    monkeypatch.setattr(worker_module, "OutboxWorker", DummyOutboxWorker)
    monkeypatch.setattr(worker_module, "CleanupRequestedConsumer", DummyConsumer)
    monkeypatch.setattr(
        worker_module,
        "engine",
        SimpleNamespace(dispose=fake_dispose),
    )
    monkeypatch.setattr(worker_module.asyncio, "get_running_loop", lambda: DummyLoop())

    async def fake_cleanup_loop(**kwargs):
        stop_event_ref["value"] = kwargs["stop_event"]
        await kwargs["stop_event"].wait()

    monkeypatch.setattr(worker_module, "_run_stale_pending_cleanup_loop", fake_cleanup_loop)

    await worker_module.run_worker()

    assert state["bucket"] is True
    assert state["publisher_connect"] is True
    assert state["outbox_run"] is True
    assert state["consumer_run"] is True
    assert state["consumer_close"] is True
    assert state["publisher_close"] is True
    assert state["engine_dispose"] is True
