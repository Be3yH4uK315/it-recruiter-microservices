from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from app.config import Settings
from app.infrastructure.web.middleware.idempotency import IdempotencyMiddleware
from app.infrastructure.web.middleware.request_id import RequestIdMiddleware


def _request(
    *,
    method: str = "POST",
    path: str = "/v1/test",
    headers: dict[str, str] | None = None,
    body: bytes = b"",
) -> Request:
    raw_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()
    ]

    received = False

    async def receive() -> dict:
        nonlocal received
        if received:
            return {"type": "http.request", "body": b"", "more_body": False}
        received = True
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": raw_headers,
        "client": ("testclient", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope, receive)


@pytest.mark.asyncio
async def test_request_id_middleware_exposes_incoming_header() -> None:
    middleware = RequestIdMiddleware(
        app=lambda scope, receive, send: None,
        settings=Settings(
            debug=False, request_id_header_name="X-Request-ID", expose_request_id_header=True
        ),
    )
    request = _request(method="GET", headers={"X-Request-ID": "req-42"})

    seen = {}

    async def call_next(req: Request) -> Response:
        seen["request_id"] = req.state.request_id
        return Response(status_code=200)

    response = await middleware.dispatch(request, call_next)

    assert seen["request_id"] == "req-42"
    assert response.headers["X-Request-ID"] == "req-42"


@pytest.mark.asyncio
async def test_request_id_middleware_generates_id_when_missing() -> None:
    middleware = RequestIdMiddleware(
        app=lambda scope, receive, send: None,
        settings=Settings(
            debug=False, request_id_header_name="X-Request-ID", expose_request_id_header=True
        ),
    )
    request = _request(method="GET")

    async def call_next(req: Request) -> Response:
        assert req.state.request_id
        return Response(status_code=200)

    response = await middleware.dispatch(request, call_next)

    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_idempotency_middleware_skips_without_key_or_method() -> None:
    middleware = IdempotencyMiddleware(
        app=lambda scope, receive, send: None,
        session_factory=object(),
    )
    request = _request(method="GET")

    async def call_next(_: Request) -> Response:
        return Response(status_code=204)

    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_idempotency_middleware_returns_conflict_for_reused_key_with_different_payload() -> (
    None
):
    middleware = IdempotencyMiddleware(
        app=lambda scope, receive, send: None,
        session_factory=object(),
        header_name="Idempotency-Key",
    )
    request = _request(
        method="POST",
        headers={"Idempotency-Key": "idem-1"},
        body=b'{"a":1}',
    )

    async def fake_existing(_: str):
        return SimpleNamespace(request_hash="another", status_code=200, response_body={"ok": True})

    middleware._get_existing_key = fake_existing  # type: ignore[method-assign]

    response = await middleware.dispatch(request, lambda _: Response(status_code=500))
    assert response.status_code == 409
    assert json.loads(response.body)["detail"] == "Idempotency key reuse with different payload"
    assert response.headers["Idempotency-Key"] == "idem-1"


@pytest.mark.asyncio
async def test_idempotency_middleware_returns_cached_204() -> None:
    middleware = IdempotencyMiddleware(
        app=lambda scope, receive, send: None,
        session_factory=object(),
        header_name="Idempotency-Key",
    )
    request = _request(method="POST", headers={"Idempotency-Key": "idem-2"}, body=b"{}")

    async def fake_existing(_: str):
        expected_hash = middleware._build_request_hash(method="POST", path="/v1/test", body=b"{}")
        return SimpleNamespace(request_hash=expected_hash, status_code=204, response_body=None)

    middleware._get_existing_key = fake_existing  # type: ignore[method-assign]

    response = await middleware.dispatch(request, lambda _: Response(status_code=500))
    assert response.status_code == 204
    assert response.headers["Idempotency-Key"] == "idem-2"


@pytest.mark.asyncio
async def test_idempotency_middleware_stores_json_response() -> None:
    middleware = IdempotencyMiddleware(
        app=lambda scope, receive, send: None,
        session_factory=object(),
        header_name="Idempotency-Key",
    )
    request = _request(method="POST", headers={"Idempotency-Key": "idem-3"}, body=b'{"x":1}')

    async def fake_missing(_: str):
        return None

    stored: dict[str, object] = {}

    async def fake_store(*, key: str, request_hash: str, response_body, status_code: int) -> None:
        stored["key"] = key
        stored["request_hash"] = request_hash
        stored["response_body"] = response_body
        stored["status_code"] = status_code

    async def call_next(_: Request) -> Response:
        payload = json.dumps({"result": "ok"}).encode("utf-8")

        async def body_iter():
            yield payload

        return StreamingResponse(body_iter(), status_code=201, media_type="application/json")

    middleware._get_existing_key = fake_missing  # type: ignore[method-assign]
    middleware._store_response = fake_store  # type: ignore[method-assign]

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 201
    assert response.headers["Idempotency-Key"] == "idem-3"
    assert stored["key"] == "idem-3"
    assert stored["response_body"] == {"result": "ok"}
