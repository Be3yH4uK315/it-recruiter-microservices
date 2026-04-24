from __future__ import annotations

import asyncio
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
    _VERIFY_ATTEMPTS = 3
    _RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

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

        response: httpx.Response | None = None
        last_error: httpx.HTTPError | None = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._internal_token}",
        }
        payload = {
            "access_token": access_token,
        }

        for attempt in range(1, self._VERIFY_ATTEMPTS + 1):
            try:
                response = await self._client.post(
                    url,
                    headers=headers,
                    json=payload,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "auth gateway verify request failed",
                    extra={
                        "base_url": self._base_url,
                        "error_type": exc.__class__.__name__,
                        "attempt": attempt,
                    },
                    exc_info=exc,
                )
                if attempt == self._VERIFY_ATTEMPTS:
                    raise AuthServiceUnavailableError("auth verify request failed") from exc
                await asyncio.sleep(0.1 * attempt)
                continue

            if response.status_code not in self._RETRYABLE_STATUS_CODES:
                break

            logger.warning(
                "auth gateway verify returned retryable status",
                extra={
                    "base_url": self._base_url,
                    "status_code": response.status_code,
                    "attempt": attempt,
                },
            )
            if attempt == self._VERIFY_ATTEMPTS:
                raise AuthServiceUnavailableError("auth service is unavailable")
            await asyncio.sleep(0.1 * attempt)

        if response is None:
            raise AuthServiceUnavailableError("auth verify request failed") from last_error

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
