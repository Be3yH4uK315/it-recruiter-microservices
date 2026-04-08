from __future__ import annotations

from datetime import datetime
from uuid import UUID

import httpx

from app.application.common.contracts import AuthGateway, AuthVerifiedSubject
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class AuthGatewayError(RuntimeError):
    pass


class InvalidAccessTokenGatewayError(AuthGatewayError):
    pass


class AuthServiceUnavailableError(AuthGatewayError):
    pass


class AuthGatewayProtocolError(AuthGatewayError):
    pass


class HttpAuthGateway(AuthGateway):
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        internal_token: str | None,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._internal_token = internal_token

    async def verify_access_token(
        self,
        *,
        access_token: str,
    ) -> AuthVerifiedSubject:
        if self._internal_token is None or not self._internal_token.strip():
            raise AuthServiceUnavailableError("internal service token is not configured")

        url = f"{self._base_url}/api/v1/internal/auth/verify"

        try:
            response = await self._client.post(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._internal_token}",
                },
                json={
                    "access_token": access_token,
                },
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "auth gateway verify request failed",
                extra={
                    "base_url": self._base_url,
                    "error_type": exc.__class__.__name__,
                },
                exc_info=exc,
            )
            raise AuthServiceUnavailableError("auth verify request failed") from exc

        if response.status_code == 401:
            raise InvalidAccessTokenGatewayError("access token is invalid")
        if response.status_code == 403:
            raise InvalidAccessTokenGatewayError("access is forbidden")
        if response.status_code >= 500:
            raise AuthServiceUnavailableError("auth service is unavailable")

        try:
            response.raise_for_status()
            payload = response.json()
            return AuthVerifiedSubject(
                user_id=UUID(str(payload["user_id"])),
                telegram_id=int(payload["telegram_id"]),
                role=str(payload["role"]),
                roles=tuple(str(item) for item in payload.get("roles", [])),
                is_active=bool(payload["is_active"]),
                expires_at=datetime.fromisoformat(
                    str(payload["expires_at"]).replace("Z", "+00:00")
                ),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "auth gateway verify response is invalid",
                extra={
                    "base_url": self._base_url,
                    "error_type": exc.__class__.__name__,
                },
                exc_info=exc,
            )
            raise AuthGatewayProtocolError("auth verify response is invalid") from exc
