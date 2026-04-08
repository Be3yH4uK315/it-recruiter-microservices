from __future__ import annotations

import uuid
from uuid import UUID

import httpx

from app.application.common.contracts import (
    UNSET,
    CandidateGateway,
    CandidateProfileSummary,
    CandidateStatisticsView,
    FileUploadUrlView,
)
from app.application.common.gateway_errors import (
    CandidateGatewayConflictError,
    CandidateGatewayError,
    CandidateGatewayForbiddenError,
    CandidateGatewayProtocolError,
    CandidateGatewayRateLimitedError,
    CandidateGatewayUnauthorizedError,
    CandidateGatewayUnavailableError,
    CandidateGatewayValidationError,
)
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class HttpCandidateGateway(CandidateGateway):
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def get_profile_by_telegram(
        self,
        *,
        access_token: str,
        telegram_id: int,
    ) -> CandidateProfileSummary | None:
        url = f"{self._base_url}/api/v1/candidates/by-telegram/{telegram_id}"

        try:
            response = await self._client.get(
                url,
                headers=self._build_bearer_headers(access_token),
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "candidate gateway get_profile_by_telegram request failed",
                extra={"base_url": self._base_url, "telegram_id": telegram_id},
                exc_info=exc,
            )
            raise CandidateGatewayUnavailableError(
                "candidate profile by telegram request failed"
            ) from exc

        if response.status_code == 404:
            return None
        if response.status_code == 401:
            raise CandidateGatewayUnauthorizedError("candidate access token is invalid")
        if response.status_code == 403:
            raise CandidateGatewayForbiddenError("candidate access forbidden")
        if response.status_code == 429:
            raise CandidateGatewayRateLimitedError("candidate rate limit exceeded")
        if response.status_code >= 500:
            raise CandidateGatewayUnavailableError("candidate service is unavailable")

        return self._parse_candidate_profile_response(response)

    async def create_candidate(
        self,
        *,
        access_token: str,
        display_name: str,
        headline_role: str,
        telegram_contact: str,
        idempotency_key: str | None = None,
    ) -> CandidateProfileSummary:
        url = f"{self._base_url}/api/v1/candidates"

        payload = {
            "display_name": display_name,
            "headline_role": headline_role,
            "contacts": {
                "telegram": telegram_contact,
            },
        }

        try:
            response = await self._client.post(
                url,
                headers=self._build_mutation_headers(
                    access_token,
                    idempotency_key=idempotency_key,
                ),
                json=payload,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "candidate gateway create_candidate request failed",
                extra={"base_url": self._base_url},
                exc_info=exc,
            )
            raise CandidateGatewayUnavailableError("candidate create request failed") from exc

        if response.status_code == 401:
            raise CandidateGatewayUnauthorizedError("candidate access token is invalid")
        if response.status_code == 403:
            raise CandidateGatewayForbiddenError("candidate create forbidden")
        if response.status_code == 409:
            raise CandidateGatewayConflictError("candidate already exists")
        if response.status_code == 422:
            raise CandidateGatewayValidationError("candidate create payload is invalid")
        if response.status_code == 429:
            raise CandidateGatewayRateLimitedError("candidate rate limit exceeded")
        if response.status_code >= 500:
            raise CandidateGatewayUnavailableError("candidate service is unavailable")

        return self._parse_candidate_profile_response(response)

    async def update_candidate_profile(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        display_name: str | None | object = UNSET,
        headline_role: str | None | object = UNSET,
        location: str | None | object = UNSET,
        work_modes: list[str] | None | object = UNSET,
        about_me: str | None | object = UNSET,
        contacts_visibility: str | None | object = UNSET,
        contacts: dict[str, str | None] | None | object = UNSET,
        status: str | None | object = UNSET,
        salary_min: int | None | object = UNSET,
        salary_max: int | None | object = UNSET,
        currency: str | None | object = UNSET,
        english_level: str | None | object = UNSET,
        skills: list[dict] | None | object = UNSET,
        education: list[dict] | None | object = UNSET,
        experiences: list[dict] | None | object = UNSET,
        projects: list[dict] | None | object = UNSET,
        idempotency_key: str | None = None,
    ) -> CandidateProfileSummary:
        url = f"{self._base_url}/api/v1/candidates/{candidate_id}"

        payload: dict[str, object] = {}
        if display_name is not UNSET:
            payload["display_name"] = display_name
        if headline_role is not UNSET:
            payload["headline_role"] = headline_role
        if location is not UNSET:
            payload["location"] = location
        if work_modes is not UNSET:
            payload["work_modes"] = work_modes
        if about_me is not UNSET:
            payload["about_me"] = about_me
        if contacts_visibility is not UNSET:
            payload["contacts_visibility"] = contacts_visibility
        if contacts is not UNSET:
            payload["contacts"] = contacts
        if status is not UNSET:
            payload["status"] = status
        if salary_min is not UNSET:
            payload["salary_min"] = salary_min
        if salary_max is not UNSET:
            payload["salary_max"] = salary_max
        if currency is not UNSET:
            payload["currency"] = currency
        if english_level is not UNSET:
            payload["english_level"] = english_level
        if skills is not UNSET:
            payload["skills"] = skills
        if education is not UNSET:
            payload["education"] = education
        if experiences is not UNSET:
            payload["experiences"] = experiences
        if projects is not UNSET:
            payload["projects"] = projects

        if not payload:
            raise CandidateGatewayError("candidate update payload is empty")

        try:
            response = await self._client.patch(
                url,
                headers=self._build_mutation_headers(
                    access_token,
                    idempotency_key=idempotency_key,
                ),
                json=payload,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "candidate gateway update_candidate_profile request failed",
                extra={"base_url": self._base_url, "candidate_id": str(candidate_id)},
                exc_info=exc,
            )
            raise CandidateGatewayUnavailableError("candidate update request failed") from exc

        if response.status_code == 401:
            raise CandidateGatewayUnauthorizedError("candidate access token is invalid")
        if response.status_code == 403:
            raise CandidateGatewayForbiddenError("candidate update forbidden")
        if response.status_code == 409:
            raise CandidateGatewayConflictError("candidate update conflict")
        if response.status_code == 422:
            raise CandidateGatewayValidationError("candidate update payload is invalid")
        if response.status_code == 429:
            raise CandidateGatewayRateLimitedError("candidate rate limit exceeded")
        if response.status_code >= 500:
            raise CandidateGatewayUnavailableError("candidate service is unavailable")

        return self._parse_candidate_profile_response(response)

    async def get_statistics(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
    ) -> CandidateStatisticsView:
        url = f"{self._base_url}/api/v1/candidates/{candidate_id}/statistics"

        try:
            response = await self._client.get(
                url,
                headers=self._build_bearer_headers(access_token),
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "candidate gateway statistics request failed",
                extra={"base_url": self._base_url, "candidate_id": str(candidate_id)},
                exc_info=exc,
            )
            raise CandidateGatewayUnavailableError("candidate statistics request failed") from exc

        if response.status_code == 401:
            raise CandidateGatewayUnauthorizedError("candidate access token is invalid")
        if response.status_code == 403:
            raise CandidateGatewayForbiddenError("candidate statistics forbidden")
        if response.status_code == 429:
            raise CandidateGatewayRateLimitedError("candidate rate limit exceeded")
        if response.status_code >= 500:
            raise CandidateGatewayUnavailableError("candidate service is unavailable")

        try:
            response.raise_for_status()
            payload = response.json()
            return CandidateStatisticsView(
                total_views=int(payload.get("total_views", 0)),
                total_likes=int(payload.get("total_likes", 0)),
                total_contact_requests=int(payload.get("total_contact_requests", 0)),
                is_degraded=bool(payload.get("is_degraded", False)),
            )
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            logger.warning(
                "candidate gateway statistics response invalid",
                extra={"base_url": self._base_url, "candidate_id": str(candidate_id)},
                exc_info=exc,
            )
            raise CandidateGatewayProtocolError("candidate statistics response invalid") from exc

    async def get_avatar_upload_url(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        filename: str,
        content_type: str,
        idempotency_key: str | None = None,
    ) -> FileUploadUrlView:
        return await self._get_upload_url(
            access_token=access_token,
            candidate_id=candidate_id,
            filename=filename,
            content_type=content_type,
            kind="avatar",
            idempotency_key=idempotency_key,
        )

    async def replace_avatar(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        file_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        await self._replace_file(
            access_token=access_token,
            candidate_id=candidate_id,
            file_id=file_id,
            kind="avatar",
            idempotency_key=idempotency_key,
        )

    async def delete_avatar(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        await self._delete_file(
            access_token=access_token,
            candidate_id=candidate_id,
            kind="avatar",
            idempotency_key=idempotency_key,
        )

    async def get_resume_upload_url(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        filename: str,
        content_type: str,
        idempotency_key: str | None = None,
    ) -> FileUploadUrlView:
        return await self._get_upload_url(
            access_token=access_token,
            candidate_id=candidate_id,
            filename=filename,
            content_type=content_type,
            kind="resume",
            idempotency_key=idempotency_key,
        )

    async def replace_resume(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        file_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        await self._replace_file(
            access_token=access_token,
            candidate_id=candidate_id,
            file_id=file_id,
            kind="resume",
            idempotency_key=idempotency_key,
        )

    async def delete_resume(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        await self._delete_file(
            access_token=access_token,
            candidate_id=candidate_id,
            kind="resume",
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def _build_bearer_headers(
        access_token: str,
    ) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

    @staticmethod
    def _build_mutation_headers(
        access_token: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, str]:
        headers = HttpCandidateGateway._build_bearer_headers(access_token)
        headers["Idempotency-Key"] = (idempotency_key or "").strip() or str(uuid.uuid4())
        return headers

    def _parse_candidate_profile_response(
        self,
        response: httpx.Response,
    ) -> CandidateProfileSummary:
        try:
            response.raise_for_status()
            payload = response.json()

            avatar_file_id_raw = payload.get("avatar_file_id")
            resume_file_id_raw = payload.get("resume_file_id")

            return CandidateProfileSummary(
                id=UUID(str(payload["id"])),
                telegram_id=int(payload["telegram_id"]),
                display_name=str(payload["display_name"]),
                headline_role=str(payload["headline_role"]),
                location=self._as_str_or_none(payload.get("location")),
                status=self._as_str_or_none(payload.get("status")),
                avatar_file_id=UUID(str(avatar_file_id_raw)) if avatar_file_id_raw else None,
                avatar_download_url=self._as_str_or_none(payload.get("avatar_download_url")),
                resume_file_id=UUID(str(resume_file_id_raw)) if resume_file_id_raw else None,
                resume_download_url=self._as_str_or_none(payload.get("resume_download_url")),
                version_id=self._as_int_or_none(payload.get("version_id")),
                work_modes=self._as_work_modes(payload.get("work_modes")),
                contacts_visibility=self._as_str_or_none(payload.get("contacts_visibility")),
                contacts=self._as_contacts_or_none(payload.get("contacts")),
                english_level=self._as_str_or_none(payload.get("english_level")),
                about_me=self._as_str_or_none(payload.get("about_me")),
                salary_min=self._as_int_or_none(payload.get("salary_min")),
                salary_max=self._as_int_or_none(payload.get("salary_max")),
                currency=self._as_str_or_none(payload.get("currency")),
                experience_years=self._as_float(payload.get("experience_years"), default=0.0),
                skills=self._as_skills(payload.get("skills")),
                education=self._as_dict_list(payload.get("education")),
                experiences=self._as_dict_list(payload.get("experiences")),
                projects=self._as_dict_list(payload.get("projects")),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "candidate gateway profile response invalid",
                extra={"base_url": self._base_url},
                exc_info=exc,
            )
            raise CandidateGatewayProtocolError("candidate profile response invalid") from exc

    async def _get_upload_url(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        filename: str,
        content_type: str,
        kind: str,
        idempotency_key: str | None = None,
    ) -> FileUploadUrlView:
        url = f"{self._base_url}/api/v1/candidates/{candidate_id}/{kind}/upload-url"
        try:
            response = await self._client.post(
                url,
                headers=self._build_mutation_headers(
                    access_token,
                    idempotency_key=idempotency_key,
                ),
                json={"filename": filename, "content_type": content_type},
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "candidate gateway upload url request failed",
                extra={"base_url": self._base_url, "candidate_id": str(candidate_id), "kind": kind},
                exc_info=exc,
            )
            raise CandidateGatewayUnavailableError("candidate upload url request failed") from exc

        if response.status_code == 401:
            raise CandidateGatewayUnauthorizedError("candidate access token is invalid")
        if response.status_code == 403:
            raise CandidateGatewayForbiddenError("candidate upload url forbidden")
        if response.status_code == 422:
            raise CandidateGatewayValidationError("candidate upload payload is invalid")
        if response.status_code == 429:
            raise CandidateGatewayRateLimitedError("candidate rate limit exceeded")
        if response.status_code >= 500:
            raise CandidateGatewayUnavailableError("candidate service is unavailable")

        try:
            response.raise_for_status()
            payload = response.json()
            headers = payload.get("headers")
            return FileUploadUrlView(
                file_id=UUID(str(payload["file_id"])),
                upload_url=str(payload["upload_url"]),
                method=str(payload.get("method") or "PUT"),
                expires_in=int(payload.get("expires_in") or 0),
                headers=headers if isinstance(headers, dict) else {},
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "candidate gateway upload url response invalid",
                extra={"base_url": self._base_url, "candidate_id": str(candidate_id), "kind": kind},
                exc_info=exc,
            )
            raise CandidateGatewayProtocolError("candidate upload url response invalid") from exc

    async def _replace_file(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        file_id: UUID,
        kind: str,
        idempotency_key: str | None = None,
    ) -> None:
        url = f"{self._base_url}/api/v1/candidates/{candidate_id}/{kind}"
        try:
            response = await self._client.put(
                url,
                headers=self._build_mutation_headers(
                    access_token,
                    idempotency_key=idempotency_key,
                ),
                json={"file_id": str(file_id)},
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "candidate gateway replace file request failed",
                extra={"base_url": self._base_url, "candidate_id": str(candidate_id), "kind": kind},
                exc_info=exc,
            )
            raise CandidateGatewayUnavailableError("candidate replace file request failed") from exc

        if response.status_code == 401:
            raise CandidateGatewayUnauthorizedError("candidate access token is invalid")
        if response.status_code == 403:
            raise CandidateGatewayForbiddenError("candidate replace file forbidden")
        if response.status_code == 409:
            raise CandidateGatewayConflictError("candidate replace file conflict")
        if response.status_code == 422:
            raise CandidateGatewayValidationError("candidate replace file payload is invalid")
        if response.status_code == 429:
            raise CandidateGatewayRateLimitedError("candidate rate limit exceeded")
        if response.status_code >= 500:
            raise CandidateGatewayUnavailableError("candidate service is unavailable")

        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "candidate gateway replace file response invalid",
                extra={"base_url": self._base_url, "candidate_id": str(candidate_id), "kind": kind},
                exc_info=exc,
            )
            raise CandidateGatewayProtocolError("candidate replace file response invalid") from exc

    async def _delete_file(
        self,
        *,
        access_token: str,
        candidate_id: UUID,
        kind: str,
        idempotency_key: str | None = None,
    ) -> None:
        url = f"{self._base_url}/api/v1/candidates/{candidate_id}/{kind}"
        try:
            response = await self._client.delete(
                url,
                headers=self._build_mutation_headers(
                    access_token,
                    idempotency_key=idempotency_key,
                ),
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "candidate gateway delete file request failed",
                extra={"base_url": self._base_url, "candidate_id": str(candidate_id), "kind": kind},
                exc_info=exc,
            )
            raise CandidateGatewayUnavailableError("candidate delete file request failed") from exc

        if response.status_code == 401:
            raise CandidateGatewayUnauthorizedError("candidate access token is invalid")
        if response.status_code == 403:
            raise CandidateGatewayForbiddenError("candidate delete file forbidden")
        if response.status_code == 404:
            return
        if response.status_code == 409:
            raise CandidateGatewayConflictError("candidate delete file conflict")
        if response.status_code == 422:
            raise CandidateGatewayValidationError("candidate delete file payload is invalid")
        if response.status_code == 429:
            raise CandidateGatewayRateLimitedError("candidate rate limit exceeded")
        if response.status_code >= 500:
            raise CandidateGatewayUnavailableError("candidate service is unavailable")

        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "candidate gateway delete file response invalid",
                extra={"base_url": self._base_url, "candidate_id": str(candidate_id), "kind": kind},
                exc_info=exc,
            )
            raise CandidateGatewayProtocolError("candidate delete file response invalid") from exc

    @staticmethod
    def _as_str_or_none(value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

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
    def _as_work_modes(value: object) -> list[str] | None:
        if not isinstance(value, list):
            return None
        result: list[str] = []
        for item in value:
            normalized = HttpCandidateGateway._as_str_or_none(item)
            if normalized:
                result.append(normalized)
        return result or None

    @staticmethod
    def _as_skills(value: object) -> list[dict] | None:
        if not isinstance(value, list):
            return None
        result = [item for item in value if isinstance(item, dict)]
        return result or None

    @staticmethod
    def _as_dict_list(value: object) -> list[dict] | None:
        if not isinstance(value, list):
            return None
        result = [item for item in value if isinstance(item, dict)]
        return result or None
