from __future__ import annotations

from datetime import datetime
from uuid import UUID

import httpx

from app.application.common.contracts import (
    AuthGateway,
    AuthSessionView,
    AuthUserView,
    AuthVerifiedSubject,
)
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class AuthGatewayError(RuntimeError):
    pass


class AuthGatewayUnauthorizedError(AuthGatewayError):
    pass


class AuthGatewayForbiddenError(AuthGatewayError):
    pass


class AuthGatewayUnavailableError(AuthGatewayError):
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

    async def login_via_bot(
        self,
        *,
        telegram_id: int,
        role: str,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        photo_url: str | None,
    ) -> AuthSessionView:
        if self._internal_token is None or not self._internal_token.strip():
            raise AuthGatewayUnavailableError("internal service token is not configured")

        url = f"{self._base_url}/api/v1/auth/login/bot"

        try:
            response = await self._client.post(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._internal_token}",
                },
                json={
                    "telegram_id": telegram_id,
                    "role": role,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "photo_url": photo_url,
                },
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "auth gateway login_via_bot request failed",
                extra={"base_url": self._base_url, "error_type": exc.__class__.__name__},
                exc_info=exc,
            )
            raise AuthGatewayUnavailableError("auth login via bot request failed") from exc

        return self._parse_auth_session_response(response, operation="login_via_bot")

    async def refresh_session(
        self,
        *,
        refresh_token: str,
    ) -> AuthSessionView:
        url = f"{self._base_url}/api/v1/auth/refresh"

        try:
            response = await self._client.post(
                url,
                headers={"Accept": "application/json"},
                json={"refresh_token": refresh_token},
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "auth gateway refresh request failed",
                extra={"base_url": self._base_url, "error_type": exc.__class__.__name__},
                exc_info=exc,
            )
            raise AuthGatewayUnavailableError("auth refresh request failed") from exc

        return self._parse_auth_session_response(response, operation="refresh")

    async def logout(
        self,
        *,
        refresh_token: str,
    ) -> None:
        url = f"{self._base_url}/api/v1/auth/logout"

        try:
            response = await self._client.post(
                url,
                headers={"Accept": "application/json"},
                json={"refresh_token": refresh_token},
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "auth gateway logout request failed",
                extra={"base_url": self._base_url, "error_type": exc.__class__.__name__},
                exc_info=exc,
            )
            raise AuthGatewayUnavailableError("auth logout request failed") from exc

        if response.status_code in {401, 403, 404, 204}:
            return
        if response.status_code >= 500:
            raise AuthGatewayUnavailableError("auth service is unavailable")

        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "auth gateway logout response failed",
                extra={
                    "base_url": self._base_url,
                    "status_code": response.status_code,
                    "error_type": exc.__class__.__name__,
                },
                exc_info=exc,
            )
            raise AuthGatewayProtocolError("auth logout response is invalid") from exc

    async def verify_access_token(
        self,
        *,
        access_token: str,
    ) -> AuthVerifiedSubject:
        if self._internal_token is None or not self._internal_token.strip():
            raise AuthGatewayUnavailableError("internal service token is not configured")

        url = f"{self._base_url}/api/v1/internal/auth/verify"

        try:
            response = await self._client.post(
                url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._internal_token}",
                },
                json={"access_token": access_token},
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "auth gateway verify request failed",
                extra={"base_url": self._base_url, "error_type": exc.__class__.__name__},
                exc_info=exc,
            )
            raise AuthGatewayUnavailableError("auth verify request failed") from exc

        if response.status_code == 401:
            raise AuthGatewayUnauthorizedError("access token is invalid")
        if response.status_code == 403:
            raise AuthGatewayForbiddenError("access is forbidden")
        if response.status_code >= 500:
            raise AuthGatewayUnavailableError("auth service is unavailable")

        try:
            response.raise_for_status()
            payload = response.json()

            roles_raw = payload.get("roles", [])
            if not isinstance(roles_raw, list):
                roles_raw = []

            return AuthVerifiedSubject(
                user_id=UUID(str(payload["user_id"])),
                telegram_id=int(payload["telegram_id"]),
                role=str(payload["role"]),
                roles=tuple(str(item) for item in roles_raw if str(item).strip()),
                is_active=bool(payload["is_active"]),
                expires_at=datetime.fromisoformat(
                    str(payload["expires_at"]).replace("Z", "+00:00")
                ),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "auth gateway verify response is invalid",
                extra={"base_url": self._base_url, "error_type": exc.__class__.__name__},
                exc_info=exc,
            )
            raise AuthGatewayProtocolError("auth verify response is invalid") from exc

    def _parse_auth_session_response(
        self,
        response: httpx.Response,
        *,
        operation: str,
    ) -> AuthSessionView:
        if response.status_code == 401:
            raise AuthGatewayUnauthorizedError(f"auth {operation} unauthorized")
        if response.status_code == 403:
            raise AuthGatewayForbiddenError(f"auth {operation} forbidden")
        if response.status_code >= 500:
            raise AuthGatewayUnavailableError("auth service is unavailable")

        try:
            response.raise_for_status()
            payload = response.json()
            user_payload = payload["user"]

            roles_raw = user_payload.get("roles", [])
            if not isinstance(roles_raw, list):
                roles_raw = []

            return AuthSessionView(
                user=AuthUserView(
                    id=UUID(str(user_payload["id"])),
                    telegram_id=int(user_payload["telegram_id"]),
                    username=user_payload.get("username"),
                    first_name=user_payload.get("first_name"),
                    last_name=user_payload.get("last_name"),
                    photo_url=user_payload.get("photo_url"),
                    role=str(user_payload["role"]),
                    roles=tuple(str(item) for item in roles_raw if str(item).strip()),
                    is_active=bool(user_payload["is_active"]),
                ),
                access_token=str(payload["access_token"]),
                refresh_token=str(payload["refresh_token"]),
                token_type=str(payload["token_type"]),
                expires_in=int(payload["expires_in"]),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "auth gateway session response is invalid",
                extra={
                    "operation": operation,
                    "base_url": self._base_url,
                    "status_code": response.status_code,
                    "error_type": exc.__class__.__name__,
                },
                exc_info=exc,
            )
            raise AuthGatewayProtocolError("auth session response is invalid") from exc
