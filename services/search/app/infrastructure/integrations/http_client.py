from __future__ import annotations

import httpx

from app.config import Settings


def build_default_async_http_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(
            settings.http_client_timeout_seconds,
            connect=min(settings.http_client_timeout_seconds, 5.0),
        ),
        limits=httpx.Limits(
            max_connections=settings.http_client_max_connections,
            max_keepalive_connections=settings.http_client_max_keepalive_connections,
            keepalive_expiry=settings.http_client_keepalive_expiry_seconds,
        ),
    )
