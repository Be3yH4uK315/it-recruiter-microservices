from __future__ import annotations

from uuid import UUID

import httpx

from app.application.common.contracts import (
    CandidateGateway,
    CandidateIdentity,
    CandidateShortProfile,
)
from app.infrastructure.integrations.circuit_breaker import (
    CircuitBreakerOpenError,
    candidate_gateway_circuit_breaker,
)
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class HttpCandidateGateway(CandidateGateway):
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

    async def get_candidate_profile(
        self,
        *,
        candidate_id: UUID,
        employer_telegram_id: int,
    ) -> CandidateShortProfile | None:
        url = f"{self._base_url}/api/v1/candidates/{candidate_id}/employer-view"

        async def _do_request() -> CandidateShortProfile | None:
            response = await self._client.get(
                url,
                headers=self._build_headers(),
                params={"employer_telegram_id": employer_telegram_id},
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            payload = response.json()

            avatar_file_id_raw = payload.get("avatar_file_id")
            resume_file_id_raw = payload.get("resume_file_id")

            return CandidateShortProfile(
                id=UUID(str(payload["id"])),
                display_name=str(payload["display_name"]),
                headline_role=str(payload["headline_role"]),
                location=self._as_str_or_none(payload.get("location")),
                work_modes=self._as_str_list(payload.get("work_modes")),
                experience_years=self._as_float(payload.get("experience_years"), default=0.0),
                contacts_visibility=self._as_str_or_none(payload.get("contacts_visibility")),
                contacts=self._as_contacts_or_none(payload.get("contacts")),
                can_view_contacts=bool(payload.get("can_view_contacts", False)),
                status=self._as_str_or_none(payload.get("status")),
                english_level=self._as_str_or_none(payload.get("english_level")),
                about_me=self._as_str_or_none(payload.get("about_me")),
                salary_min=self._as_int_or_none(payload.get("salary_min")),
                salary_max=self._as_int_or_none(payload.get("salary_max")),
                currency=self._as_str_or_none(payload.get("currency")),
                skills=self._normalize_skills(payload.get("skills")),
                education=self._normalize_education(payload.get("education")),
                experiences=self._normalize_experiences(payload.get("experiences")),
                projects=self._normalize_projects(payload.get("projects")),
                avatar_file_id=UUID(str(avatar_file_id_raw)) if avatar_file_id_raw else None,
                avatar_download_url=self._as_str_or_none(payload.get("avatar_download_url")),
                resume_file_id=UUID(str(resume_file_id_raw)) if resume_file_id_raw else None,
                resume_download_url=self._as_str_or_none(payload.get("resume_download_url")),
                created_at=self._as_str_or_none(payload.get("created_at")),
                updated_at=self._as_str_or_none(payload.get("updated_at")),
                version_id=self._as_int_or_none(payload.get("version_id")),
                explanation=None,
                match_score=0.0,
            )

        try:
            return await candidate_gateway_circuit_breaker.call(_do_request)
        except CircuitBreakerOpenError:
            logger.warning(
                "candidate gateway request skipped because circuit breaker is open",
                extra={
                    "base_url": self._base_url,
                    "candidate_id": str(candidate_id),
                },
            )
            return None
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "candidate gateway request failed",
                extra={
                    "base_url": self._base_url,
                    "candidate_id": str(candidate_id),
                    "error_type": exc.__class__.__name__,
                },
                exc_info=exc,
            )
            return None

    async def get_candidate_identity(
        self,
        *,
        telegram_id: int,
    ) -> CandidateIdentity | None:
        url = f"{self._base_url}/api/v1/internal/candidates/by-telegram/{telegram_id}"

        async def _do_request() -> CandidateIdentity | None:
            response = await self._client.get(
                url,
                headers=self._build_headers(),
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            payload = response.json()

            return CandidateIdentity(
                candidate_id=UUID(str(payload["id"])),
                telegram_id=int(payload["telegram_id"]),
                status=self._as_str_or_none(payload.get("status")),
            )

        try:
            return await candidate_gateway_circuit_breaker.call(_do_request)
        except CircuitBreakerOpenError:
            logger.warning(
                "candidate identity request skipped because circuit breaker is open",
                extra={
                    "base_url": self._base_url,
                    "telegram_id": telegram_id,
                },
            )
            return None
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "candidate identity request failed",
                extra={
                    "base_url": self._base_url,
                    "telegram_id": telegram_id,
                    "error_type": exc.__class__.__name__,
                },
                exc_info=exc,
            )
            return None

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
    def _as_float(value: object, *, default: float = 0.0) -> float:
        if value is None or isinstance(value, bool):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_str_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []

        result: list[str] = []
        for item in value:
            text = HttpCandidateGateway._as_str_or_none(item)
            if text is not None:
                result.append(text)
        return result

    @staticmethod
    def _as_list_of_dicts(value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def _as_contacts_or_none(value: object) -> dict[str, str | None] | None:
        if not isinstance(value, dict):
            return None

        result: dict[str, str | None] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            result[key] = HttpCandidateGateway._as_str_or_none(item)

        return result or None

    @staticmethod
    def _normalize_skills(value: object) -> list[dict[str, object]]:
        items = HttpCandidateGateway._as_list_of_dicts(value)
        result: list[dict[str, object]] = []

        for item in items:
            skill = HttpCandidateGateway._as_str_or_none(item.get("skill"))
            kind = HttpCandidateGateway._as_str_or_none(item.get("kind"))
            level = HttpCandidateGateway._as_int_or_none(item.get("level"))

            if skill is None or kind is None:
                continue

            normalized: dict[str, object] = {
                "skill": skill,
                "kind": kind,
            }
            if level is not None:
                normalized["level"] = level

            result.append(normalized)

        return result

    @staticmethod
    def _normalize_education(value: object) -> list[dict[str, object]]:
        items = HttpCandidateGateway._as_list_of_dicts(value)
        result: list[dict[str, object]] = []

        for item in items:
            level = HttpCandidateGateway._as_str_or_none(item.get("level"))
            institution = HttpCandidateGateway._as_str_or_none(item.get("institution"))
            year = HttpCandidateGateway._as_int_or_none(item.get("year"))

            if level is None or institution is None or year is None:
                continue

            result.append(
                {
                    "level": level,
                    "institution": institution,
                    "year": year,
                }
            )

        return result

    @staticmethod
    def _normalize_experiences(value: object) -> list[dict[str, object]]:
        items = HttpCandidateGateway._as_list_of_dicts(value)
        result: list[dict[str, object]] = []

        for item in items:
            company = HttpCandidateGateway._as_str_or_none(item.get("company"))
            position = HttpCandidateGateway._as_str_or_none(item.get("position"))
            start_date = HttpCandidateGateway._as_str_or_none(item.get("start_date"))
            end_date = HttpCandidateGateway._as_str_or_none(item.get("end_date"))
            responsibilities = HttpCandidateGateway._as_str_or_none(item.get("responsibilities"))

            if company is None or position is None or start_date is None:
                continue

            normalized: dict[str, object] = {
                "company": company,
                "position": position,
                "start_date": start_date,
            }
            if end_date is not None:
                normalized["end_date"] = end_date
            if responsibilities is not None:
                normalized["responsibilities"] = responsibilities

            result.append(normalized)

        return result

    @staticmethod
    def _normalize_projects(value: object) -> list[dict[str, object]]:
        items = HttpCandidateGateway._as_list_of_dicts(value)
        result: list[dict[str, object]] = []

        for item in items:
            title = HttpCandidateGateway._as_str_or_none(item.get("title"))
            description = HttpCandidateGateway._as_str_or_none(item.get("description"))
            links_raw = item.get("links")

            if title is None:
                continue

            links: list[str] = []
            if isinstance(links_raw, list):
                for link in links_raw:
                    normalized_link = HttpCandidateGateway._as_str_or_none(link)
                    if normalized_link is not None:
                        links.append(normalized_link)

            normalized: dict[str, object] = {
                "title": title,
                "links": links,
            }
            if description is not None:
                normalized["description"] = description

            result.append(normalized)

        return result
