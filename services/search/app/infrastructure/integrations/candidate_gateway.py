from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

import httpx

from app.application.common.contracts import CandidateDocumentPayload, CandidateGateway
from app.application.common.exceptions import IntegrationApplicationError


@dataclass(slots=True)
class HttpCandidateGateway(CandidateGateway):
    client: httpx.AsyncClient
    base_url: str
    internal_token: str | None = None

    async def get_candidate_profile(
        self,
        *,
        candidate_id: UUID,
    ) -> CandidateDocumentPayload | None:
        response = await self._request(
            "GET",
            f"/api/v1/internal/candidates/{candidate_id}/search-document",
        )

        if response.status_code == 404:
            return None

        data = self._parse_json(response)
        if not isinstance(data, dict):
            raise IntegrationApplicationError(
                "candidate service returned invalid candidate payload",
            )

        return self._to_payload(data)

    async def list_candidates(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[CandidateDocumentPayload]:
        response = await self._request(
            "GET",
            "/api/v1/internal/candidates/search-documents",
            params={"limit": limit, "offset": offset},
        )

        data = self._parse_json(response)
        if not isinstance(data, dict):
            raise IntegrationApplicationError(
                "candidate service returned invalid candidate list payload",
            )

        items = data.get("items")
        if not isinstance(items, list):
            raise IntegrationApplicationError(
                "candidate service returned invalid candidate items payload",
            )

        result: list[CandidateDocumentPayload] = []
        for item in items:
            if isinstance(item, dict):
                result.append(self._to_payload(item))

        return result

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = f"{self.base_url.rstrip('/')}{path}"
        headers = self._build_headers()

        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise IntegrationApplicationError(
                f"candidate service request failed: {exc}",
            ) from exc

        if response.status_code >= 500:
            raise IntegrationApplicationError(
                f"candidate service returned {response.status_code}",
            )

        if response.status_code >= 400 and response.status_code != 404:
            raise IntegrationApplicationError(
                f"candidate service returned {response.status_code}: {response.text}",
            )

        return response

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if self.internal_token:
            headers["Authorization"] = f"Bearer {self.internal_token}"
        return headers

    @staticmethod
    def _parse_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    @classmethod
    def _to_payload(cls, data: dict[str, Any]) -> CandidateDocumentPayload:
        try:
            candidate_id = UUID(str(data["id"]))
        except (KeyError, ValueError) as exc:
            raise IntegrationApplicationError(
                "candidate payload does not contain valid id",
            ) from exc

        experiences = cls._safe_list_of_dicts(data.get("experiences"))
        projects = cls._safe_list_of_dicts(data.get("projects"))
        education = cls._safe_list_of_dicts(data.get("education"))
        skills = cls._safe_skill_list(data.get("skills"))
        work_modes = cls._safe_str_list(data.get("work_modes"))

        experience_years = cls._safe_float(data.get("experience_years"))
        if experience_years is None:
            experience_years = cls._calculate_experience_years(experiences)

        return CandidateDocumentPayload(
            id=candidate_id,
            display_name=str(data.get("display_name") or ""),
            headline_role=str(data.get("headline_role") or ""),
            location=cls._safe_optional_str(data.get("location")),
            work_modes=work_modes,
            experience_years=experience_years,
            skills=skills,
            salary_min=cls._safe_int(data.get("salary_min")),
            salary_max=cls._safe_int(data.get("salary_max")),
            currency=cls._safe_optional_str(data.get("currency")),
            english_level=cls._safe_optional_str(data.get("english_level")),
            about_me=cls._safe_optional_str(data.get("about_me")),
            experiences=experiences,
            projects=projects,
            education=education,
            status=cls._safe_optional_str(data.get("status")),
        )

    @staticmethod
    def _safe_optional_str(value: Any) -> str | None:
        if value is None:
            return None

        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if value is None or isinstance(value, bool):
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_str_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []

        result: list[str] = []
        for item in value:
            normalized = HttpCandidateGateway._safe_optional_str(item)
            if normalized is not None:
                result.append(normalized)
        return result

    @staticmethod
    def _safe_list_of_dicts(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    @staticmethod
    def _safe_skill_list(value: Any) -> list[dict[str, Any] | str]:
        if not isinstance(value, list):
            return []

        result: list[dict[str, Any] | str] = []
        for item in value:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str):
                normalized = item.strip()
                if normalized:
                    result.append(normalized)
        return result

    @staticmethod
    def _calculate_experience_years(experiences: list[dict[str, Any]]) -> float:
        if not experiences:
            return 0.0

        ranges: list[tuple[date, date]] = []
        today = date.today()

        for item in experiences:
            start_raw = item.get("start_date")
            end_raw = item.get("end_date")

            if not start_raw:
                continue

            try:
                start_date = datetime.fromisoformat(str(start_raw)).date()
            except ValueError:
                try:
                    start_date = date.fromisoformat(str(start_raw))
                except ValueError:
                    continue

            if end_raw:
                try:
                    end_date = datetime.fromisoformat(str(end_raw)).date()
                except ValueError:
                    try:
                        end_date = date.fromisoformat(str(end_raw))
                    except ValueError:
                        end_date = today
            else:
                end_date = today

            if end_date < start_date:
                continue

            ranges.append((start_date, end_date))

        if not ranges:
            return 0.0

        ranges.sort(key=lambda item: item[0])

        merged: list[tuple[date, date]] = []
        current_start, current_end = ranges[0]

        for start_date, end_date in ranges[1:]:
            if start_date <= current_end:
                if end_date > current_end:
                    current_end = end_date
                continue

            merged.append((current_start, current_end))
            current_start, current_end = start_date, end_date

        merged.append((current_start, current_end))

        total_days = sum((end_date - start_date).days for start_date, end_date in merged)
        return round(total_days / 365.25, 2)
