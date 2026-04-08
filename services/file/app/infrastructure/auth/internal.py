from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import get_settings


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    prefix = "bearer "
    if not authorization.lower().startswith(prefix):
        return None

    return authorization[len(prefix) :].strip() or None


async def require_internal_service(
    authorization: str | None = Header(default=None),
) -> None:
    settings = get_settings()

    if not settings.internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal service authentication is not configured.",
        )

    token = _extract_bearer_token(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing internal service token. Use Authorization: Bearer <token>.",
        )

    if token != settings.internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service token.",
        )
