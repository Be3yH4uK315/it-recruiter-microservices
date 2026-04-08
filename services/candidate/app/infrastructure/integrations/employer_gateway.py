from __future__ import annotations

from uuid import UUID

import httpx

from app.application.common.contracts import EmployerGateway
from app.infrastructure.integrations.circuit_breaker import (
    CircuitBreakerOpenError,
    employer_gateway_circuit_breaker,
)
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class HttpEmployerGateway(EmployerGateway):
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        internal_token: str | None = None,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._internal_token = internal_token

    async def has_contact_access(
        self,
        *,
        candidate_id: UUID,
        employer_telegram_id: int,
    ) -> bool:
        url = f"{self._base_url}/api/v1/internal/contact-access"

        async def _do_request() -> bool:
            response = await self._client.get(
                url,
                headers=self._build_headers(),
                params={
                    "candidate_id": str(candidate_id),
                    "employer_telegram_id": employer_telegram_id,
                },
            )
            response.raise_for_status()

            payload = response.json()
            return bool(payload.get("has_access", False))

        try:
            return await employer_gateway_circuit_breaker.call(_do_request)
        except CircuitBreakerOpenError:
            logger.warning(
                "employer gateway access request skipped because circuit breaker is open",
                extra={
                    "base_url": self._base_url,
                    "candidate_id": str(candidate_id),
                    "employer_telegram_id": employer_telegram_id,
                },
            )
            return False
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "employer gateway access request failed",
                extra={
                    "base_url": self._base_url,
                    "candidate_id": str(candidate_id),
                    "employer_telegram_id": employer_telegram_id,
                    "error_type": exc.__class__.__name__,
                },
                exc_info=exc,
            )
            return False

    async def get_candidate_statistics(self, *, candidate_id: UUID) -> dict[str, int | bool]:
        url = f"{self._base_url}/api/v1/internal/candidates/{candidate_id}/statistics"

        async def _do_request() -> dict[str, int | bool]:
            response = await self._client.get(
                url,
                headers=self._build_headers(),
            )
            response.raise_for_status()

            payload = response.json()
            return {
                "total_views": int(payload.get("total_views", 0)),
                "total_likes": int(payload.get("total_likes", 0)),
                "total_contact_requests": int(payload.get("total_contact_requests", 0)),
                "is_degraded": False,
            }

        try:
            return await employer_gateway_circuit_breaker.call(_do_request)
        except CircuitBreakerOpenError:
            logger.warning(
                "employer gateway statistics request skipped because circuit breaker is open",
                extra={
                    "base_url": self._base_url,
                    "candidate_id": str(candidate_id),
                },
            )
            return {
                "total_views": 0,
                "total_likes": 0,
                "total_contact_requests": 0,
                "is_degraded": True,
            }
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "employer gateway statistics request failed",
                extra={
                    "base_url": self._base_url,
                    "candidate_id": str(candidate_id),
                    "error_type": exc.__class__.__name__,
                },
                exc_info=exc,
            )
            return {
                "total_views": 0,
                "total_likes": 0,
                "total_contact_requests": 0,
                "is_degraded": True,
            }

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if self._internal_token:
            headers["Authorization"] = f"Bearer {self._internal_token}"
        return headers
