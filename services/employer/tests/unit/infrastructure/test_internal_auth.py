from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.application.common.contracts import AuthVerifiedSubject
from app.config import Settings
from app.infrastructure.auth.internal import (
    _extract_bearer_token,
    require_employer_subject,
    require_internal_service,
)


def test_extract_bearer_token() -> None:
    assert _extract_bearer_token("Bearer token-123") == "token-123"
    assert _extract_bearer_token("bearer token-123") == "token-123"
    assert _extract_bearer_token("Basic abc") is None
    assert _extract_bearer_token(None) is None


@pytest.mark.asyncio
async def test_require_internal_service_rejects_invalid_token() -> None:
    settings = Settings(internal_service_token="expected-token", debug=False)
    with pytest.raises(HTTPException) as exc:
        await require_internal_service(
            settings=settings,
            authorization="Bearer wrong-token",
        )

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_employer_subject_returns_telegram_id() -> None:
    subject = AuthVerifiedSubject(
        user_id=uuid4(),
        telegram_id=1001,
        role="employer",
        roles=("employer",),
        is_active=True,
        expires_at=datetime.now(timezone.utc),
    )

    result = await require_employer_subject(subject=subject)
    assert result == 1001
