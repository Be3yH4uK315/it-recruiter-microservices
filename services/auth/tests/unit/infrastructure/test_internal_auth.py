from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.infrastructure.auth.internal import (
    _extract_bearer_token,
    require_internal_service,
)


def test_extract_bearer_token_returns_token() -> None:
    assert _extract_bearer_token("Bearer secret-token") == "secret-token"


def test_extract_bearer_token_returns_token_for_lowercase_prefix() -> None:
    assert _extract_bearer_token("bearer secret-token") == "secret-token"


def test_extract_bearer_token_returns_none_for_missing_header() -> None:
    assert _extract_bearer_token(None) is None


def test_extract_bearer_token_returns_none_for_invalid_prefix() -> None:
    assert _extract_bearer_token("Basic secret-token") is None


def test_extract_bearer_token_returns_none_for_empty_token() -> None:
    assert _extract_bearer_token("Bearer   ") is None


@pytest.mark.asyncio
async def test_require_internal_service_accepts_valid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-internal-token")

    from app.config import get_settings

    get_settings.cache_clear()

    await require_internal_service("Bearer test-internal-token")


@pytest.mark.asyncio
async def test_require_internal_service_rejects_missing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-internal-token")

    from app.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        await require_internal_service(None)

    assert exc_info.value.status_code == 401
    assert (
        exc_info.value.detail
        == "Missing internal service token. Use Authorization: Bearer <token>."
    )


@pytest.mark.asyncio
async def test_require_internal_service_rejects_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-internal-token")

    from app.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        await require_internal_service("Bearer wrong-token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid internal service token."
