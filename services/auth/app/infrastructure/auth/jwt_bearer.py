from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.application.auth.services.jwt_service import JwtService
from app.config import get_settings
from app.domain.auth.errors import InvalidAccessTokenError
from app.domain.auth.value_objects import AccessTokenClaims


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    prefix = "bearer "
    if not authorization.lower().startswith(prefix):
        return None

    return authorization[len(prefix) :].strip() or None


async def require_access_token_claims(
    authorization: str | None = Header(default=None),
) -> AccessTokenClaims:
    settings = get_settings()
    jwt_service = JwtService(settings)

    token = _extract_bearer_token(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token. Use Authorization: Bearer <token>.",
        )

    try:
        return jwt_service.decode_access_token(token)
    except InvalidAccessTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
        ) from exc
