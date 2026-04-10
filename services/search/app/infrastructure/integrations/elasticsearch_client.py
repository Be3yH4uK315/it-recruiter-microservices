from __future__ import annotations

from typing import Any

from app.config import Settings

try:
    from elasticsearch import AsyncElasticsearch
except ModuleNotFoundError as exc:  # pragma: no cover - env-dependent import
    AsyncElasticsearch = Any  # type: ignore[assignment]
    _ELASTICSEARCH_IMPORT_ERROR = exc
else:
    _ELASTICSEARCH_IMPORT_ERROR = None


def build_elasticsearch_client(settings: Settings) -> AsyncElasticsearch:
    if _ELASTICSEARCH_IMPORT_ERROR is not None:
        raise RuntimeError(
            "elasticsearch dependency is not installed"
        ) from _ELASTICSEARCH_IMPORT_ERROR
    return AsyncElasticsearch(
        settings.elasticsearch_url,
        request_timeout=settings.elasticsearch_request_timeout_seconds,
    )
