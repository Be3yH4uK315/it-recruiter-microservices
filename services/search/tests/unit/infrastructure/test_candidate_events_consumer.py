from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from app.infrastructure.messaging.candidate_events_consumer import (
    CandidateEventsConsumer,
)


class FakeHttpResponse:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text


class FakeHttpClient:
    def __init__(self):
        self.post_calls = []
        self.delete_calls = []
        self.raise_on_post = False
        self.raise_on_delete = False

    async def post(self, url, headers=None, timeout=None):
        if self.raise_on_post:
            raise RuntimeError("post failed")
        self.post_calls.append((url, headers, timeout))
        return FakeHttpResponse()

    async def delete(self, url, headers=None, timeout=None):
        if self.raise_on_delete:
            raise RuntimeError("delete failed")
        self.delete_calls.append((url, headers, timeout))
        return FakeHttpResponse()


class FakeIncomingMessage:
    def __init__(self, *, body: bytes, routing_key: str) -> None:
        self.body = body
        self.routing_key = routing_key
        self.acked = False
        self.rejected_with: bool | None = None

    async def ack(self) -> None:
        self.acked = True

    async def reject(self, requeue: bool = False) -> None:
        self.rejected_with = requeue


def make_settings():
    return SimpleNamespace(
        search_service_url="http://search-api:8000",
        internal_service_token="super-secret-internal-token",
        internal_index_callback_timeout_seconds=60.0,
        rabbitmq_url="amqp://guest:guest@rabbitmq:5672/",
        candidate_exchange_name="candidate.events",
        candidate_queue_name="search_service_queue",
        rabbitmq_prefetch_count=1,
        rabbitmq_reconnect_delay_seconds=5.0,
    )


async def test_consumer_calls_upsert_endpoint() -> None:
    candidate_id = uuid4()
    http_client = FakeHttpClient()

    consumer = CandidateEventsConsumer(
        settings=make_settings(),
        http_client=http_client,
    )

    await consumer._call_upsert(candidate_id)

    assert len(http_client.post_calls) == 1
    url, headers, timeout = http_client.post_calls[0]
    assert url.endswith(f"/api/v1/internal/index/candidates/{candidate_id}")
    assert headers["Authorization"] == "Bearer super-secret-internal-token"
    assert timeout == 60.0


async def test_consumer_calls_delete_endpoint() -> None:
    candidate_id = uuid4()
    http_client = FakeHttpClient()

    consumer = CandidateEventsConsumer(
        settings=make_settings(),
        http_client=http_client,
    )

    await consumer._call_delete(candidate_id)

    assert len(http_client.delete_calls) == 1
    url, headers, timeout = http_client.delete_calls[0]
    assert url.endswith(f"/api/v1/internal/index/candidates/{candidate_id}")
    assert headers["Authorization"] == "Bearer super-secret-internal-token"
    assert timeout == 60.0


def test_consumer_decodes_valid_message_body() -> None:
    consumer = CandidateEventsConsumer(
        settings=make_settings(),
        http_client=FakeHttpClient(),
    )

    body = json.dumps({"candidate_id": str(uuid4()), "operation": "upsert"}).encode()
    decoded = consumer._decode_message_body(body)

    assert decoded is not None
    assert decoded["operation"] == "upsert"


def test_consumer_extracts_candidate_id() -> None:
    candidate_id = uuid4()

    consumer = CandidateEventsConsumer(
        settings=make_settings(),
        http_client=FakeHttpClient(),
    )

    extracted = consumer._extract_candidate_id({"candidate_id": str(candidate_id)})
    assert extracted == candidate_id


async def test_consumer_acks_invalid_payload() -> None:
    message = FakeIncomingMessage(body=b"not-json", routing_key="candidate.updated")
    consumer = CandidateEventsConsumer(
        settings=make_settings(),
        http_client=FakeHttpClient(),
    )

    await consumer._handle_message(message)

    assert message.acked is True
    assert message.rejected_with is None


async def test_consumer_requeues_when_dispatch_fails() -> None:
    candidate_id = uuid4()
    message = FakeIncomingMessage(
        body=json.dumps({"candidate_id": str(candidate_id)}).encode(),
        routing_key="search.candidate.sync.requested",
    )
    http_client = FakeHttpClient()
    http_client.raise_on_post = True
    consumer = CandidateEventsConsumer(
        settings=make_settings(),
        http_client=http_client,
    )

    try:
        await consumer._handle_message(message)
    except RuntimeError as exc:
        assert str(exc) == "post failed"
    else:
        raise AssertionError("expected dispatch failure")

    assert message.acked is False
    assert message.rejected_with is True


async def test_consumer_skips_deprecated_duplicate_events() -> None:
    candidate_id = uuid4()
    message = FakeIncomingMessage(
        body=json.dumps({"candidate_id": str(candidate_id)}).encode(),
        routing_key="candidate.created",
    )
    http_client = FakeHttpClient()
    consumer = CandidateEventsConsumer(
        settings=make_settings(),
        http_client=http_client,
    )

    await consumer._handle_message(message)

    assert message.acked is True
    assert message.rejected_with is None
    assert http_client.post_calls == []
