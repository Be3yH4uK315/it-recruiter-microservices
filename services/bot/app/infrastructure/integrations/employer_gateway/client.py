from __future__ import annotations

import uuid
from uuid import UUID

import httpx

from app.application.common.contracts import (
    UNSET,
    CandidatePendingContactRequestView,
    CandidateProfileSummary,
    ContactAccessResultView,
    ContactRequestDecisionView,
    ContactRequestDetailsView,
    EmployerGateway,
    EmployerProfileSummary,
    EmployerStatisticsView,
    FileUploadUrlView,
    NextCandidateResultView,
    SearchSessionSummary,
)
from app.application.common.gateway_errors import (
    EmployerGatewayConflictError,
    EmployerGatewayError,
    EmployerGatewayForbiddenError,
    EmployerGatewayNotFoundError,
    EmployerGatewayProtocolError,
    EmployerGatewayRateLimitedError,
    EmployerGatewayUnauthorizedError,
    EmployerGatewayUnavailableError,
    EmployerGatewayValidationError,
)
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class HttpEmployerGateway(EmployerGateway):
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def get_by_telegram(
        self,
        *,
        access_token: str,
        telegram_id: int,
    ) -> EmployerProfileSummary | None:
        url = f"{self._base_url}/api/v1/employers/by-telegram/{telegram_id}"

        try:
            response = await self._client.get(
                url,
                headers=self._build_bearer_headers(access_token),
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "employer gateway get_by_telegram request failed",
                extra={"base_url": self._base_url, "telegram_id": telegram_id},
                exc_info=exc,
            )
            raise EmployerGatewayUnavailableError("employer by telegram request failed") from exc

        if response.status_code == 404:
            return None
        if response.status_code == 401:
            raise EmployerGatewayUnauthorizedError("employer access token is invalid")
        if response.status_code == 403:
            raise EmployerGatewayForbiddenError("employer access forbidden")
        if response.status_code == 429:
            raise EmployerGatewayRateLimitedError("employer rate limit exceeded")
        if response.status_code >= 500:
            raise EmployerGatewayUnavailableError("employer service is unavailable")

        return self._parse_profile_response(response)

    async def create_employer(
        self,
        *,
        access_token: str,
        telegram_id: int,
        company: str | None,
        idempotency_key: str | None = None,
    ) -> EmployerProfileSummary:
        url = f"{self._base_url}/api/v1/employers"

        payload = {
            "telegram_id": telegram_id,
            "company": company,
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
                "employer gateway create_employer request failed",
                extra={"base_url": self._base_url, "telegram_id": telegram_id},
                exc_info=exc,
            )
            raise EmployerGatewayUnavailableError("employer create request failed") from exc

        if response.status_code == 401:
            raise EmployerGatewayUnauthorizedError("employer access token is invalid")
        if response.status_code == 403:
            raise EmployerGatewayForbiddenError("employer create forbidden")
        if response.status_code == 409:
            raise EmployerGatewayConflictError("employer already exists")
        if response.status_code == 422:
            raise EmployerGatewayValidationError("employer create payload is invalid")
        if response.status_code == 429:
            raise EmployerGatewayRateLimitedError("employer rate limit exceeded")
        if response.status_code >= 500:
            raise EmployerGatewayUnavailableError("employer service is unavailable")

        return self._parse_profile_response(response)

    async def update_employer(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        company: str | None | object = UNSET,
        contacts: dict[str, str | None] | None | object = UNSET,
        idempotency_key: str | None = None,
    ) -> EmployerProfileSummary:
        url = f"{self._base_url}/api/v1/employers/{employer_id}"

        payload: dict[str, object] = {}
        if company is not UNSET:
            payload["company"] = company
        if contacts is not UNSET:
            payload["contacts"] = contacts
        if not payload:
            raise EmployerGatewayError("employer update payload is empty")

        response = await self._request(
            "PATCH",
            url,
            access_token=access_token,
            json=payload,
            idempotency_key=idempotency_key,
        )
        if response.status_code == 404:
            raise EmployerGatewayNotFoundError("employer not found")
        return self._parse_profile_response(response)

    async def get_statistics(
        self,
        *,
        access_token: str,
        employer_id: UUID,
    ) -> EmployerStatisticsView:
        url = f"{self._base_url}/api/v1/employers/{employer_id}/statistics"

        try:
            response = await self._client.get(
                url,
                headers=self._build_bearer_headers(access_token),
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "employer gateway statistics request failed",
                extra={"base_url": self._base_url, "employer_id": str(employer_id)},
                exc_info=exc,
            )
            raise EmployerGatewayUnavailableError("employer statistics request failed") from exc

        if response.status_code == 401:
            raise EmployerGatewayUnauthorizedError("employer access token is invalid")
        if response.status_code == 403:
            raise EmployerGatewayForbiddenError("employer statistics forbidden")
        if response.status_code == 429:
            raise EmployerGatewayRateLimitedError("employer rate limit exceeded")
        if response.status_code >= 500:
            raise EmployerGatewayUnavailableError("employer service is unavailable")

        try:
            response.raise_for_status()
            payload = response.json()
            return EmployerStatisticsView(
                total_viewed=int(payload.get("total_viewed", 0)),
                total_liked=int(payload.get("total_liked", 0)),
                total_contact_requests=int(payload.get("total_contact_requests", 0)),
                total_contacts_granted=int(payload.get("total_contacts_granted", 0)),
            )
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            logger.warning(
                "employer gateway statistics response invalid",
                extra={"base_url": self._base_url, "employer_id": str(employer_id)},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("employer statistics response invalid") from exc

    async def create_search_session(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        title: str,
        filters: dict[str, object],
        idempotency_key: str | None = None,
    ) -> SearchSessionSummary:
        url = f"{self._base_url}/api/v1/employers/{employer_id}/searches"

        payload = {
            "title": title,
            "filters": filters,
        }

        response = await self._request(
            "POST",
            url,
            access_token=access_token,
            json=payload,
            idempotency_key=idempotency_key,
        )
        return self._parse_search_session(response)

    async def list_searches(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        limit: int = 10,
    ) -> list[SearchSessionSummary]:
        url = f"{self._base_url}/api/v1/employers/{employer_id}/searches"

        response = await self._request(
            "GET",
            url,
            access_token=access_token,
            params={"limit": limit},
        )

        try:
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise TypeError("searches response must be list")
            return [
                self._parse_search_session_item(item) for item in payload if isinstance(item, dict)
            ]
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            logger.warning(
                "employer gateway list_searches response invalid",
                extra={"base_url": self._base_url, "employer_id": str(employer_id)},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("employer searches response invalid") from exc

    async def pause_search_session(
        self,
        *,
        access_token: str,
        session_id: UUID,
        idempotency_key: str | None = None,
    ) -> SearchSessionSummary:
        return await self._set_search_session_status(
            access_token=access_token,
            session_id=session_id,
            operation="pause",
            idempotency_key=idempotency_key,
        )

    async def resume_search_session(
        self,
        *,
        access_token: str,
        session_id: UUID,
        idempotency_key: str | None = None,
    ) -> SearchSessionSummary:
        return await self._set_search_session_status(
            access_token=access_token,
            session_id=session_id,
            operation="resume",
            idempotency_key=idempotency_key,
        )

    async def close_search_session(
        self,
        *,
        access_token: str,
        session_id: UUID,
        idempotency_key: str | None = None,
    ) -> SearchSessionSummary:
        return await self._set_search_session_status(
            access_token=access_token,
            session_id=session_id,
            operation="close",
            idempotency_key=idempotency_key,
        )

    async def get_next_candidate(
        self,
        *,
        access_token: str,
        session_id: UUID,
    ) -> NextCandidateResultView:
        url = f"{self._base_url}/api/v1/searches/{session_id}/next"

        response = await self._request(
            "GET",
            url,
            access_token=access_token,
        )

        try:
            response.raise_for_status()
            payload = response.json()
            candidate_payload = payload.get("candidate")
            message = payload.get("message")
            candidate = (
                self._parse_candidate_summary(candidate_payload)
                if isinstance(candidate_payload, dict)
                else None
            )
            return NextCandidateResultView(
                candidate=candidate,
                message=str(message).strip() if message is not None else None,
                is_degraded=bool(payload.get("is_degraded", False)),
            )
        except (httpx.HTTPError, TypeError, ValueError, KeyError) as exc:
            logger.warning(
                "employer gateway get_next_candidate response invalid",
                extra={"base_url": self._base_url, "session_id": str(session_id)},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("next candidate response invalid") from exc

    async def submit_decision(
        self,
        *,
        access_token: str,
        session_id: UUID,
        candidate_id: UUID,
        decision: str,
        note: str | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        url = f"{self._base_url}/api/v1/searches/{session_id}/decisions"
        payload = {
            "candidate_id": str(candidate_id),
            "decision": decision,
            "note": note,
        }

        response = await self._request(
            "POST",
            url,
            access_token=access_token,
            json=payload,
            idempotency_key=idempotency_key,
        )

        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "employer gateway submit_decision response invalid",
                extra={"base_url": self._base_url, "session_id": str(session_id)},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("submit decision response invalid") from exc

    async def get_favorites(
        self,
        *,
        access_token: str,
        employer_id: UUID,
    ) -> list[CandidateProfileSummary]:
        url = f"{self._base_url}/api/v1/contacts/favorites/{employer_id}"

        response = await self._request(
            "GET",
            url,
            access_token=access_token,
        )

        try:
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise TypeError("favorites response must be list")
            return [
                self._parse_candidate_summary(item) for item in payload if isinstance(item, dict)
            ]
        except (httpx.HTTPError, TypeError, ValueError, KeyError) as exc:
            logger.warning(
                "employer gateway favorites response invalid",
                extra={"base_url": self._base_url, "employer_id": str(employer_id)},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("favorites response invalid") from exc

    async def get_unlocked_contacts(
        self,
        *,
        access_token: str,
        employer_id: UUID,
    ) -> list[CandidateProfileSummary]:
        url = f"{self._base_url}/api/v1/contacts/unlocked/{employer_id}"

        response = await self._request(
            "GET",
            url,
            access_token=access_token,
        )

        try:
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise TypeError("unlocked contacts response must be list")
            return [
                self._parse_candidate_summary(item) for item in payload if isinstance(item, dict)
            ]
        except (httpx.HTTPError, TypeError, ValueError, KeyError) as exc:
            logger.warning(
                "employer gateway unlocked contacts response invalid",
                extra={"base_url": self._base_url, "employer_id": str(employer_id)},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("unlocked contacts response invalid") from exc

    async def request_contact_access(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        candidate_id: UUID,
        idempotency_key: str | None = None,
    ) -> ContactAccessResultView:
        url = f"{self._base_url}/api/v1/contacts/requests/{employer_id}"
        payload = {
            "candidate_id": str(candidate_id),
        }

        response = await self._request(
            "POST",
            url,
            access_token=access_token,
            json=payload,
            idempotency_key=idempotency_key,
        )

        try:
            response.raise_for_status()
            payload = response.json()

            request_id_raw = payload.get("request_id")
            request_id = None
            if request_id_raw:
                request_id = UUID(str(request_id_raw))

            contacts_raw = payload.get("contacts")
            contacts = contacts_raw if isinstance(contacts_raw, dict) else None

            notification_info_raw = payload.get("notification_info")
            notification_info = (
                notification_info_raw if isinstance(notification_info_raw, dict) else None
            )

            return ContactAccessResultView(
                granted=bool(payload.get("granted", False)),
                status=str(payload.get("status", "not_found")),
                contacts=contacts,
                request_id=request_id,
                notification_info=notification_info,
            )
        except (httpx.HTTPError, TypeError, ValueError, KeyError) as exc:
            logger.warning(
                "employer gateway request_contact_access response invalid",
                extra={
                    "base_url": self._base_url,
                    "employer_id": str(employer_id),
                    "candidate_id": str(candidate_id),
                },
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("request contact access response invalid") from exc

    async def get_avatar_upload_url(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        filename: str,
        content_type: str,
        idempotency_key: str | None = None,
    ) -> FileUploadUrlView:
        return await self._get_upload_url(
            access_token=access_token,
            employer_id=employer_id,
            filename=filename,
            content_type=content_type,
            kind="avatar",
            idempotency_key=idempotency_key,
        )

    async def replace_avatar(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        file_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        await self._replace_file(
            access_token=access_token,
            employer_id=employer_id,
            file_id=file_id,
            kind="avatar",
            idempotency_key=idempotency_key,
        )

    async def delete_avatar(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        await self._delete_file(
            access_token=access_token,
            employer_id=employer_id,
            kind="avatar",
            idempotency_key=idempotency_key,
        )

    async def get_document_upload_url(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        filename: str,
        content_type: str,
        idempotency_key: str | None = None,
    ) -> FileUploadUrlView:
        return await self._get_upload_url(
            access_token=access_token,
            employer_id=employer_id,
            filename=filename,
            content_type=content_type,
            kind="document",
            idempotency_key=idempotency_key,
        )

    async def replace_document(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        file_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        await self._replace_file(
            access_token=access_token,
            employer_id=employer_id,
            file_id=file_id,
            kind="document",
            idempotency_key=idempotency_key,
        )

    async def delete_document(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        idempotency_key: str | None = None,
    ) -> None:
        await self._delete_file(
            access_token=access_token,
            employer_id=employer_id,
            kind="document",
            idempotency_key=idempotency_key,
        )

    async def get_contact_request_details_for_candidate(
        self,
        *,
        access_token: str,
        request_id: UUID,
    ) -> ContactRequestDetailsView:
        url = f"{self._base_url}/api/v1/contacts/requests/{request_id}"
        response = await self._request(
            "GET",
            url,
            access_token=access_token,
        )
        if response.status_code == 404:
            raise EmployerGatewayNotFoundError("contact request not found")
        try:
            response.raise_for_status()
            payload = response.json()
            return ContactRequestDetailsView(
                id=UUID(str(payload["id"])),
                employer_telegram_id=int(payload["employer_telegram_id"]),
                candidate_name=str(payload["candidate_name"]),
                candidate_id=UUID(str(payload["candidate_id"])),
                status=str(payload["status"]),
                granted=bool(payload["granted"]),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "employer gateway contact request details response invalid",
                extra={"base_url": self._base_url, "request_id": str(request_id)},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("contact request details response invalid") from exc

    async def list_candidate_pending_contact_requests(
        self,
        *,
        access_token: str,
        limit: int = 10,
    ) -> list[CandidatePendingContactRequestView]:
        url = f"{self._base_url}/api/v1/contacts/requests/candidate/pending"
        response = await self._request(
            "GET",
            url,
            access_token=access_token,
            params={"limit": max(1, min(limit, 20))},
        )
        try:
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise TypeError("candidate pending contact requests response must be list")

            result: list[CandidatePendingContactRequestView] = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                result.append(
                    CandidatePendingContactRequestView(
                        id=UUID(str(item["id"])),
                        employer_id=UUID(str(item["employer_id"])),
                        employer_company=str(item.get("employer_company") or "Компания"),
                        employer_telegram_id=int(item["employer_telegram_id"]),
                        status=str(item["status"]),
                        granted=bool(item["granted"]),
                        created_at=self._as_str_or_none(item.get("created_at")),
                    )
                )
            return result
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "employer gateway candidate pending contact requests response invalid",
                extra={"base_url": self._base_url, "limit": limit},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError(
                "candidate pending contact requests response invalid"
            ) from exc

    async def respond_contact_request(
        self,
        *,
        access_token: str,
        request_id: UUID,
        granted: bool,
        idempotency_key: str | None = None,
    ) -> ContactRequestDecisionView:
        url = f"{self._base_url}/api/v1/contacts/requests/{request_id}/candidate-response"
        response = await self._request(
            "PATCH",
            url,
            access_token=access_token,
            json={"granted": granted},
            idempotency_key=idempotency_key,
        )
        if response.status_code == 404:
            raise EmployerGatewayNotFoundError("contact request not found")
        try:
            response.raise_for_status()
            payload = response.json()
            return ContactRequestDecisionView(
                granted=bool(payload["granted"]),
                status=str(payload["status"]),
                request_id=UUID(str(payload["request_id"])),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "employer gateway contact request decision response invalid",
                extra={"base_url": self._base_url, "request_id": str(request_id)},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("contact request decision response invalid") from exc

    async def _request(
        self,
        method: str,
        url: str,
        *,
        access_token: str,
        json: dict | None = None,
        params: dict | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        try:
            response = await self._client.request(
                method,
                url,
                headers=(
                    self._build_mutation_headers(
                        access_token,
                        idempotency_key=idempotency_key,
                    )
                    if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
                    else self._build_bearer_headers(access_token)
                ),
                json=json,
                params=params,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "employer gateway request failed",
                extra={"base_url": self._base_url, "url": url, "method": method},
                exc_info=exc,
            )
            raise EmployerGatewayUnavailableError("employer request failed") from exc

        if response.status_code == 401:
            raise EmployerGatewayUnauthorizedError("employer access token is invalid")
        if response.status_code == 403:
            raise EmployerGatewayForbiddenError("employer access forbidden")
        if response.status_code == 409:
            raise EmployerGatewayConflictError("employer request conflict")
        if response.status_code == 422:
            raise EmployerGatewayValidationError("employer payload is invalid")
        if response.status_code == 429:
            raise EmployerGatewayRateLimitedError("employer rate limit exceeded")
        if response.status_code >= 500:
            raise EmployerGatewayUnavailableError("employer service is unavailable")

        return response

    @staticmethod
    def _build_bearer_headers(access_token: str) -> dict[str, str]:
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
        headers = HttpEmployerGateway._build_bearer_headers(access_token)
        headers["Idempotency-Key"] = (idempotency_key or "").strip() or str(uuid.uuid4())
        return headers

    def _parse_profile_response(
        self,
        response: httpx.Response,
    ) -> EmployerProfileSummary:
        try:
            response.raise_for_status()
            payload = response.json()

            avatar_file_id_raw = payload.get("avatar_file_id")
            document_file_id_raw = payload.get("document_file_id")

            return EmployerProfileSummary(
                id=UUID(str(payload["id"])),
                telegram_id=int(payload["telegram_id"]),
                company=self._as_str_or_none(payload.get("company")),
                avatar_file_id=UUID(str(avatar_file_id_raw)) if avatar_file_id_raw else None,
                avatar_download_url=self._as_str_or_none(payload.get("avatar_download_url")),
                document_file_id=UUID(str(document_file_id_raw)) if document_file_id_raw else None,
                document_download_url=self._as_str_or_none(payload.get("document_download_url")),
                contacts=self._as_contacts_or_none(payload.get("contacts")),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "employer gateway profile response invalid",
                extra={"base_url": self._base_url},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("employer profile response invalid") from exc

    def _parse_search_session(
        self,
        response: httpx.Response,
    ) -> SearchSessionSummary:
        try:
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("search session response must be dict")
            return self._parse_search_session_item(payload)
        except (httpx.HTTPError, TypeError, ValueError, KeyError) as exc:
            logger.warning(
                "employer gateway search session response invalid",
                extra={"base_url": self._base_url},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("search session response invalid") from exc

    def _parse_search_session_item(self, payload: dict) -> SearchSessionSummary:
        filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
        return SearchSessionSummary(
            id=UUID(str(payload["id"])),
            employer_id=UUID(str(payload["employer_id"])),
            title=str(payload["title"]),
            status=str(payload["status"]),
            role=str(filters.get("role", "")),
            created_at=self._as_str_or_none(payload.get("created_at")),
            updated_at=self._as_str_or_none(payload.get("updated_at")),
        )

    def _parse_candidate_summary(self, payload: dict) -> CandidateProfileSummary:
        avatar_file_id_raw = payload.get("avatar_file_id")
        resume_file_id_raw = payload.get("resume_file_id")

        telegram_id = payload.get("telegram_id")
        telegram_id_value = None
        if telegram_id is not None:
            try:
                telegram_id_value = int(telegram_id)
            except (TypeError, ValueError):
                telegram_id_value = None

        match_score_raw = payload.get("match_score", 0.0)
        try:
            match_score = float(match_score_raw)
        except (TypeError, ValueError):
            match_score = 0.0

        return CandidateProfileSummary(
            id=UUID(str(payload["id"])),
            telegram_id=telegram_id_value,
            display_name=str(payload["display_name"]),
            headline_role=str(payload["headline_role"]),
            location=self._as_str_or_none(payload.get("location")),
            status=self._as_str_or_none(payload.get("status")),
            avatar_file_id=UUID(str(avatar_file_id_raw)) if avatar_file_id_raw else None,
            avatar_download_url=self._as_str_or_none(payload.get("avatar_download_url")),
            resume_file_id=UUID(str(resume_file_id_raw)) if resume_file_id_raw else None,
            resume_download_url=self._as_str_or_none(payload.get("resume_download_url")),
            version_id=self._as_int_or_none(payload.get("version_id")),
            experience_years=self._as_float(payload.get("experience_years"), default=0.0),
            work_modes=self._as_work_modes(payload.get("work_modes")),
            contacts_visibility=self._as_str_or_none(payload.get("contacts_visibility")),
            contacts=self._as_contacts_or_none(payload.get("contacts")),
            can_view_contacts=bool(payload.get("can_view_contacts", False)),
            english_level=self._as_str_or_none(payload.get("english_level")),
            about_me=self._as_str_or_none(payload.get("about_me")),
            salary_min=self._as_int_or_none(payload.get("salary_min")),
            salary_max=self._as_int_or_none(payload.get("salary_max")),
            currency=self._as_str_or_none(payload.get("currency")),
            skills=self._as_skills(payload.get("skills")),
            education=self._as_dict_list(payload.get("education")),
            experiences=self._as_dict_list(payload.get("experiences")),
            projects=self._as_dict_list(payload.get("projects")),
            explanation=(
                payload.get("explanation") if isinstance(payload.get("explanation"), dict) else None
            ),
            match_score=match_score,
        )

    async def _get_upload_url(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        filename: str,
        content_type: str,
        kind: str,
        idempotency_key: str | None = None,
    ) -> FileUploadUrlView:
        url = f"{self._base_url}/api/v1/employers/{employer_id}/{kind}/upload-url"
        response = await self._request(
            "POST",
            url,
            access_token=access_token,
            json={"filename": filename, "content_type": content_type},
            idempotency_key=idempotency_key,
        )
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
                "employer gateway upload url response invalid",
                extra={"base_url": self._base_url, "employer_id": str(employer_id), "kind": kind},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("employer upload url response invalid") from exc

    async def _replace_file(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        file_id: UUID,
        kind: str,
        idempotency_key: str | None = None,
    ) -> None:
        url = f"{self._base_url}/api/v1/employers/{employer_id}/{kind}"
        response = await self._request(
            "PUT",
            url,
            access_token=access_token,
            json={"file_id": str(file_id)},
            idempotency_key=idempotency_key,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "employer gateway replace file response invalid",
                extra={"base_url": self._base_url, "employer_id": str(employer_id), "kind": kind},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("employer replace file response invalid") from exc

    async def _delete_file(
        self,
        *,
        access_token: str,
        employer_id: UUID,
        kind: str,
        idempotency_key: str | None = None,
    ) -> None:
        url = f"{self._base_url}/api/v1/employers/{employer_id}/{kind}"
        response = await self._request(
            "DELETE",
            url,
            access_token=access_token,
            idempotency_key=idempotency_key,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "employer gateway delete file response invalid",
                extra={"base_url": self._base_url, "employer_id": str(employer_id), "kind": kind},
                exc_info=exc,
            )
            raise EmployerGatewayProtocolError("employer delete file response invalid") from exc

    async def _set_search_session_status(
        self,
        *,
        access_token: str,
        session_id: UUID,
        operation: str,
        idempotency_key: str | None = None,
    ) -> SearchSessionSummary:
        url = f"{self._base_url}/api/v1/searches/{session_id}/{operation}"
        response = await self._request(
            "POST",
            url,
            access_token=access_token,
            idempotency_key=idempotency_key,
        )
        if response.status_code == 404:
            raise EmployerGatewayNotFoundError("search session not found")
        return self._parse_search_session(response)

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
            result[key] = HttpEmployerGateway._as_str_or_none(item)
        return result or None

    @staticmethod
    def _as_skills(value: object) -> list[dict] | None:
        if not isinstance(value, list):
            return None
        result = [item for item in value if isinstance(item, dict)]
        return result or None

    @staticmethod
    def _as_work_modes(value: object) -> list[str] | None:
        if not isinstance(value, list):
            return None
        result: list[str] = []
        for item in value:
            normalized = HttpEmployerGateway._as_str_or_none(item)
            if normalized:
                result.append(normalized)
        return result or None

    @staticmethod
    def _as_dict_list(value: object) -> list[dict] | None:
        if not isinstance(value, list):
            return None
        result = [item for item in value if isinstance(item, dict)]
        return result or None
