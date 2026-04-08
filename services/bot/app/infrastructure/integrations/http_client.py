from __future__ import annotations

import httpx

from app.config import Settings
from app.infrastructure.observability.metrics import (
    mark_downstream_end,
    mark_downstream_start,
)


async def _on_request(request: httpx.Request) -> None:
    mark_downstream_start(request)


async def _on_response(response: httpx.Response) -> None:
    mark_downstream_end(response.request, response)


def build_default_async_http_client(settings: Settings) -> httpx.AsyncClient:
    limits = httpx.Limits(
        max_connections=settings.http_client_max_connections,
        max_keepalive_connections=settings.http_client_max_keepalive_connections,
        keepalive_expiry=settings.http_client_keepalive_expiry_seconds,
    )

    timeout = httpx.Timeout(
        connect=settings.http_client_connect_timeout_seconds,
        read=settings.http_client_read_timeout_seconds,
        write=settings.http_client_write_timeout_seconds,
        pool=settings.http_client_pool_timeout_seconds,
    )

    return httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=False,
        event_hooks={
            "request": [_on_request],
            "response": [_on_response],
        },
        headers={
            "User-Agent": f"{settings.app_name}/{settings.app_version}",
            "Accept": "application/json",
        },
    )
