from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

import httpx

from app.application.common.contracts import (
    DownloadUrlResult,
    FileGateway,
    FileMetadata,
    UploadUrlResult,
)
from app.domain.candidate.errors import IntegrationUnavailableError
from app.infrastructure.integrations.circuit_breaker import (
    CircuitBreakerOpenError,
    file_gateway_circuit_breaker,
)
from app.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class HttpFileGateway(FileGateway):
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
        self._owner_service = "candidate-service"

    async def get_avatar_upload_url(
        self,
        *,
        owner_id: UUID,
        filename: str,
        content_type: str,
    ) -> UploadUrlResult:
        return await self._get_upload_url(
            owner_id=owner_id,
            filename=filename,
            content_type=content_type,
            category="candidate_avatar",
        )

    async def get_resume_upload_url(
        self,
        *,
        owner_id: UUID,
        filename: str,
        content_type: str,
    ) -> UploadUrlResult:
        return await self._get_upload_url(
            owner_id=owner_id,
            filename=filename,
            content_type=content_type,
            category="candidate_resume",
        )

    async def get_file_metadata(
        self,
        *,
        file_id: UUID,
    ) -> FileMetadata:
        url = f"{self._base_url}/api/v1/internal/files/{file_id}"

        async def _do_request() -> FileMetadata:
            response = await self._client.get(
                url,
                headers=self._build_headers(),
                params={"owner_service": self._owner_service},
            )
            response.raise_for_status()
            return self._parse_file_metadata(response.json())

        return await self._call_with_resilience(
            _do_request,
            operation_name="file metadata request",
            extra={"file_id": str(file_id)},
            unavailable_message="Failed to get file metadata from file service",
        )

    async def complete_file_upload(
        self,
        *,
        file_id: UUID,
    ) -> FileMetadata:
        url = f"{self._base_url}/api/v1/internal/files/{file_id}/complete"

        async def _do_request() -> FileMetadata:
            response = await self._client.post(
                url,
                json={},
                headers=self._build_headers(),
            )
            response.raise_for_status()
            return await self.get_file_metadata(file_id=file_id)

        return await self._call_with_resilience(
            _do_request,
            operation_name="file complete request",
            extra={"file_id": str(file_id)},
            unavailable_message="Failed to complete file upload in file service",
        )

    async def cleanup_file(
        self,
        *,
        file_id: UUID,
        reason: str,
    ) -> None:
        url = f"{self._base_url}/api/v1/internal/files/{file_id}/cleanup"
        payload = {
            "reason": reason,
            "requested_by_service": self._owner_service,
        }

        async def _do_request() -> None:
            response = await self._client.post(
                url,
                json=payload,
                headers=self._build_headers(),
            )
            response.raise_for_status()

        await self._call_with_resilience(
            _do_request,
            operation_name="file cleanup request",
            extra={"file_id": str(file_id), "reason": reason},
            unavailable_message="Failed to cleanup file in file service",
        )

    async def get_file_download_url(
        self,
        *,
        file_id: UUID,
        owner_id: UUID,
    ) -> DownloadUrlResult:
        url = f"{self._base_url}/api/v1/internal/files/{file_id}/download-url"

        async def _do_request() -> DownloadUrlResult:
            response = await self._client.get(
                url,
                headers=self._build_headers(),
                params={
                    "owner_service": self._owner_service,
                    "owner_id": str(owner_id),
                },
            )
            response.raise_for_status()

            data = response.json()
            return DownloadUrlResult(
                file_id=UUID(str(data["file_id"])),
                download_url=str(data["download_url"]),
                method=str(data.get("method", "GET")),
                expires_in=int(data.get("expires_in", 0)),
            )

        return await self._call_with_resilience(
            _do_request,
            operation_name="file download url request",
            extra={"file_id": str(file_id), "owner_id": str(owner_id)},
            unavailable_message="Failed to get file download url from file service",
        )

    async def _get_upload_url(
        self,
        *,
        owner_id: UUID,
        filename: str,
        content_type: str,
        category: str,
    ) -> UploadUrlResult:
        url = f"{self._base_url}/api/v1/internal/files/upload-url"
        payload = {
            "owner_service": self._owner_service,
            "owner_id": str(owner_id),
            "filename": filename,
            "content_type": content_type,
            "category": category,
        }

        async def _do_request() -> UploadUrlResult:
            response = await self._client.post(
                url,
                json=payload,
                headers=self._build_headers(),
            )
            response.raise_for_status()

            data = response.json()
            return UploadUrlResult(
                file_id=UUID(str(data["file_id"])),
                upload_url=str(data["upload_url"]),
                method=str(data.get("method", "PUT")),
                expires_in=int(data.get("expires_in", 0)),
                headers=(
                    dict(data.get("headers", {})) if isinstance(data.get("headers"), dict) else {}
                ),
            )

        return await self._call_with_resilience(
            _do_request,
            operation_name="file upload url request",
            extra={
                "owner_id": str(owner_id),
                "category": category,
            },
            unavailable_message="Failed to get upload url from file service",
        )

    async def _call_with_resilience(
        self,
        func: Callable[[], Awaitable[T]],
        *,
        operation_name: str,
        extra: dict[str, str],
        unavailable_message: str,
    ) -> T:
        try:
            return await file_gateway_circuit_breaker.call(func)
        except CircuitBreakerOpenError as exc:
            logger.warning(
                f"{operation_name} skipped because circuit breaker is open",
                extra={"base_url": self._base_url, **extra},
            )
            raise IntegrationUnavailableError("File service is temporarily unavailable") from exc
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            logger.warning(
                f"{operation_name} failed",
                extra={
                    "base_url": self._base_url,
                    "error_type": exc.__class__.__name__,
                    **extra,
                },
                exc_info=exc,
            )
            raise IntegrationUnavailableError(unavailable_message) from exc

    @staticmethod
    def _parse_file_metadata(data: dict) -> FileMetadata:
        owner_id_raw = data.get("owner_id")

        return FileMetadata(
            id=UUID(str(data["id"])),
            owner_service=str(data["owner_service"]),
            owner_id=UUID(str(owner_id_raw)) if owner_id_raw is not None else None,
            category=str(data["category"]),
            status=str(data["status"]),
            filename=str(data["filename"]),
            content_type=str(data["content_type"]),
            size_bytes=int(data["size_bytes"]) if data.get("size_bytes") is not None else None,
        )

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
        }
        if self._internal_token:
            headers["Authorization"] = f"Bearer {self._internal_token}"
        return headers
