from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx

from app.application.common.contracts import AuthGateway, AuthVerifiedSubject
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class AuthGatewayError(RuntimeError):
    pass


class AuthGatewayInvalidTokenError(AuthGatewayError):
    pass


class AuthGatewayForbiddenError(AuthGatewayError):
    pass


class AuthGatewayUnavailableError(AuthGatewayError):
    pass


@dataclass(slots=True, frozen=True)
class _CachedSubject:
    subject: AuthVerifiedSubject
    valid_until: datetime


class HttpAuthGateway(AuthGateway):
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        internal_token: str | None,
        cache_ttl_seconds: int = 15,
        cache_max_entries: int = 1024,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._internal_token = internal_token
        self._cache_ttl_seconds = max(cache_ttl_seconds, 0)
        self._cache_max_entries = max(cache_max_entries, 1)
        self._verified_subject_cache: OrderedDict[str, _CachedSubject] = OrderedDict()

    async def verify_access_token(
        self,
        *,
        access_token: str,
    ) -> AuthVerifiedSubject:
        if self._internal_token is None or not self._internal_token.strip():
            raise AuthGatewayError("internal service token is not configured")

        cached_subject = self._get_cached_subject(access_token)
        if cached_subject is not None:
            return cached_subject

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
            raise AuthGatewayInvalidTokenError("access token is invalid")
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

            subject = AuthVerifiedSubject(
                user_id=UUID(str(payload["user_id"])),
                telegram_id=int(payload["telegram_id"]),
                role=str(payload["role"]),
                roles=tuple(str(item) for item in roles_raw if str(item).strip()),
                is_active=bool(payload["is_active"]),
                expires_at=datetime.fromisoformat(
                    str(payload["expires_at"]).replace("Z", "+00:00")
                ),
            )
            self._cache_subject(access_token, subject)
            return subject
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "auth gateway verify response is invalid",
                extra={"base_url": self._base_url, "error_type": exc.__class__.__name__},
                exc_info=exc,
            )
            raise AuthGatewayError("auth verify response is invalid") from exc

    def _get_cached_subject(self, access_token: str) -> AuthVerifiedSubject | None:
        cached = self._verified_subject_cache.get(access_token)
        if cached is None:
            return None

        now = datetime.now(timezone.utc)
        if cached.valid_until <= now:
            self._verified_subject_cache.pop(access_token, None)
            return None

        self._verified_subject_cache.move_to_end(access_token)
        return cached.subject

    def _cache_subject(self, access_token: str, subject: AuthVerifiedSubject) -> None:
        if self._cache_ttl_seconds <= 0:
            return

        now = datetime.now(timezone.utc)
        subject_expiry = subject.expires_at
        if subject_expiry.tzinfo is None:
            subject_expiry = subject_expiry.replace(tzinfo=timezone.utc)
        else:
            subject_expiry = subject_expiry.astimezone(timezone.utc)

        valid_until = min(subject_expiry, now + timedelta(seconds=self._cache_ttl_seconds))
        if valid_until <= now:
            return

        self._verified_subject_cache[access_token] = _CachedSubject(
            subject=subject,
            valid_until=valid_until,
        )
        self._verified_subject_cache.move_to_end(access_token)

        while len(self._verified_subject_cache) > self._cache_max_entries:
            self._verified_subject_cache.popitem(last=False)
