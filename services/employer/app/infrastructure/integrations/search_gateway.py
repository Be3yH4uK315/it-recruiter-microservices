from __future__ import annotations

from uuid import UUID

import httpx

from app.application.common.contracts import (
    SearchCandidateResult,
    SearchCandidatesBatchResult,
    SearchGateway,
)
from app.infrastructure.integrations.circuit_breaker import (
    CircuitBreakerOpenError,
    search_gateway_circuit_breaker,
)
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class HttpSearchGateway(SearchGateway):
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

    async def search_candidates(
        self,
        *,
        filters: dict,
        limit: int,
    ) -> SearchCandidatesBatchResult:
        url = f"{self._base_url}/api/v1/search/candidates"
        payload = {
            "filters": filters,
            "limit": limit,
        }

        async def _do_request() -> SearchCandidatesBatchResult:
            response = await self._client.post(
                url,
                json=payload,
                headers=self._build_headers(),
            )
            response.raise_for_status()

            data = response.json()
            raw_items = data.get("items", [])

            if not isinstance(raw_items, list):
                raise TypeError("search response items must be a list")

            items = [
                SearchCandidateResult(
                    candidate_id=UUID(str(item["candidate_id"])),
                    display_name=str(item["display_name"]),
                    headline_role=str(item["headline_role"]),
                    experience_years=float(item.get("experience_years", 0.0)),
                    location=self._as_str_or_none(item.get("location")),
                    skills=self._as_skills(item.get("skills")),
                    salary_min=self._as_int_or_none(item.get("salary_min")),
                    salary_max=self._as_int_or_none(item.get("salary_max")),
                    currency=self._as_str_or_none(item.get("currency")),
                    english_level=self._as_str_or_none(item.get("english_level")),
                    about_me=self._as_str_or_none(item.get("about_me")),
                    match_score=float(item.get("match_score", 0.0)),
                    explanation=(
                        item.get("explanation")
                        if isinstance(item.get("explanation"), dict)
                        or item.get("explanation") is None
                        else None
                    ),
                )
                for item in raw_items
                if isinstance(item, dict)
            ]

            total_raw = data.get("total", len(items))
            total = int(total_raw)

            return SearchCandidatesBatchResult(
                total=max(total, len(items)),
                items=items,
                is_degraded=False,
            )

        try:
            return await search_gateway_circuit_breaker.call(_do_request)
        except CircuitBreakerOpenError:
            logger.warning(
                "search gateway request skipped because circuit breaker is open",
                extra={"base_url": self._base_url},
            )
            return SearchCandidatesBatchResult(
                total=0,
                items=[],
                is_degraded=True,
            )
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "search gateway request failed",
                extra={
                    "base_url": self._base_url,
                    "error_type": exc.__class__.__name__,
                },
                exc_info=exc,
            )
            return SearchCandidatesBatchResult(
                total=0,
                items=[],
                is_degraded=True,
            )

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if self._internal_token:
            headers["Authorization"] = f"Bearer {self._internal_token}"
        return headers

    @staticmethod
    def _as_str_or_none(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _as_int_or_none(value: object) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_skills(value: object) -> list[dict[str, object] | str]:
        if not isinstance(value, list):
            return []

        result: list[dict[str, object] | str] = []
        for item in value:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str):
                normalized = item.strip()
                if normalized:
                    result.append(normalized)
        return result
