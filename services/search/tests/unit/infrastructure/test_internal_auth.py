from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.infrastructure.auth.internal import (
    _extract_bearer_token,
    require_internal_service,
)


def test_extract_bearer_token_returns_none_for_missing_header() -> None:
    assert _extract_bearer_token(None) is None


def test_extract_bearer_token_returns_none_for_invalid_scheme() -> None:
    assert _extract_bearer_token("Basic abc") is None


def test_extract_bearer_token_extracts_token_case_insensitive() -> None:
    assert _extract_bearer_token("Bearer secret") == "secret"
    assert _extract_bearer_token("bearer secret") == "secret"


@pytest.mark.asyncio
async def test_require_internal_service_accepts_valid_token(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.auth.internal.get_settings",
        lambda: SimpleNamespace(internal_service_token="secret"),
    )

    await require_internal_service("Bearer secret")


@pytest.mark.asyncio
async def test_require_internal_service_rejects_missing_config(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.auth.internal.get_settings",
        lambda: SimpleNamespace(internal_service_token=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_internal_service("Bearer secret")

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_require_internal_service_rejects_invalid_token(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.auth.internal.get_settings",
        lambda: SimpleNamespace(internal_service_token="secret"),
    )

    with pytest.raises(HTTPException) as exc_info:
        await require_internal_service("Bearer wrong")

    assert exc_info.value.status_code == 401
