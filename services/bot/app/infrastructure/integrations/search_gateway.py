from __future__ import annotations

import httpx

from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class SearchGatewayError(RuntimeError):
    pass


class HttpSearchGateway:
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

    async def healthcheck(self) -> dict | None:
        try:
            response = await self._client.get(
                f"{self._base_url}/api/v1/health",
                headers={"Accept": "application/json"},
            )
            if response.status_code >= 400:
                return None
            payload = response.json()
            return payload if isinstance(payload, dict) else None
        except Exception as exc:
            logger.warning(
                "search gateway healthcheck failed",
                extra={"base_url": self._base_url},
                exc_info=exc,
            )
            return None
