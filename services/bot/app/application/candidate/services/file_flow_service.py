from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.common.contracts import CandidateGateway
from app.application.common.telegram_file_flow import (
    BaseTelegramFileFlowService,
    TelegramUploadSource,
)
from app.infrastructure.db.repositories.pending_uploads import PendingUploadRepository
from app.infrastructure.telegram.client import TelegramApiClient
from app.schemas.telegram import TelegramMessage

ROLE_CANDIDATE = "candidate"
TARGET_SERVICE_CANDIDATE = "candidate"

TARGET_KIND_CANDIDATE_AVATAR = "candidate_avatar"
TARGET_KIND_CANDIDATE_RESUME = "candidate_resume"

_ALLOWED_RESUME_MIME_BY_EXTENSION: dict[str, str] = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class CandidateFileFlowError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class CandidateUploadResult:
    target_kind: str
    file_id: UUID


class CandidateFileFlowService(BaseTelegramFileFlowService):
    _flow_error_cls = CandidateFileFlowError

    def __init__(
        self,
        *,
        session: AsyncSession,
        http_client: httpx.AsyncClient,
        telegram_client: TelegramApiClient,
        candidate_gateway: CandidateGateway,
    ) -> None:
        super().__init__(http_client=http_client, telegram_client=telegram_client)
        self._session = session
        self._candidate_gateway = candidate_gateway
        self._pending_uploads = PendingUploadRepository(session)

    async def process_avatar_upload(
        self,
        *,
        access_token: str,
        telegram_user_id: int,
        candidate_id: UUID,
        message: TelegramMessage,
    ) -> CandidateUploadResult:
        source = self._extract_avatar_source(message)
        if source is None:
            raise CandidateFileFlowError("Для аватара отправь фото или документ-изображение.")

        upload = await self._candidate_gateway.get_avatar_upload_url(
            access_token=access_token,
            candidate_id=candidate_id,
            filename=source.filename,
            content_type=source.content_type,
        )

        pending = await self._pending_uploads.create(
            telegram_user_id=telegram_user_id,
            role_context=ROLE_CANDIDATE,
            target_service=TARGET_SERVICE_CANDIDATE,
            target_kind=TARGET_KIND_CANDIDATE_AVATAR,
            owner_id=candidate_id,
            file_id=upload.file_id,
            filename=source.filename,
            content_type=source.content_type,
            telegram_file_id=source.telegram_file_id,
            telegram_file_unique_id=source.telegram_file_unique_id,
        )

        try:
            content = await self._download_telegram_file(source.telegram_file_id)
            await self._pending_uploads.set_status(
                model=pending,
                status="telegram_downloaded",
            )

            await self._upload_to_presigned_url(
                upload_url=upload.upload_url,
                method=upload.method,
                headers=upload.headers,
                content_type=source.content_type,
                content=content,
            )
            await self._pending_uploads.set_status(
                model=pending,
                status="storage_uploaded",
            )

            await self._candidate_gateway.replace_avatar(
                access_token=access_token,
                candidate_id=candidate_id,
                file_id=upload.file_id,
            )
            await self._pending_uploads.set_status(
                model=pending,
                status="linked",
            )
            return CandidateUploadResult(
                target_kind=TARGET_KIND_CANDIDATE_AVATAR,
                file_id=upload.file_id,
            )
        except Exception as exc:
            await self._pending_uploads.set_status(
                model=pending,
                status="failed",
                error_message=str(exc)[:1000],
            )
            raise

    async def process_resume_upload(
        self,
        *,
        access_token: str,
        telegram_user_id: int,
        candidate_id: UUID,
        message: TelegramMessage,
    ) -> CandidateUploadResult:
        source = self._extract_resume_source(message)
        if source is None:
            raise CandidateFileFlowError("Для резюме отправь документ в формате PDF, DOC или DOCX.")

        upload = await self._candidate_gateway.get_resume_upload_url(
            access_token=access_token,
            candidate_id=candidate_id,
            filename=source.filename,
            content_type=source.content_type,
        )

        pending = await self._pending_uploads.create(
            telegram_user_id=telegram_user_id,
            role_context=ROLE_CANDIDATE,
            target_service=TARGET_SERVICE_CANDIDATE,
            target_kind=TARGET_KIND_CANDIDATE_RESUME,
            owner_id=candidate_id,
            file_id=upload.file_id,
            filename=source.filename,
            content_type=source.content_type,
            telegram_file_id=source.telegram_file_id,
            telegram_file_unique_id=source.telegram_file_unique_id,
        )

        try:
            content = await self._download_telegram_file(source.telegram_file_id)
            await self._pending_uploads.set_status(
                model=pending,
                status="telegram_downloaded",
            )

            await self._upload_to_presigned_url(
                upload_url=upload.upload_url,
                method=upload.method,
                headers=upload.headers,
                content_type=source.content_type,
                content=content,
            )
            await self._pending_uploads.set_status(
                model=pending,
                status="storage_uploaded",
            )

            await self._candidate_gateway.replace_resume(
                access_token=access_token,
                candidate_id=candidate_id,
                file_id=upload.file_id,
            )
            await self._pending_uploads.set_status(
                model=pending,
                status="linked",
            )
            return CandidateUploadResult(
                target_kind=TARGET_KIND_CANDIDATE_RESUME,
                file_id=upload.file_id,
            )
        except Exception as exc:
            await self._pending_uploads.set_status(
                model=pending,
                status="failed",
                error_message=str(exc)[:1000],
            )
            raise

    def _extract_avatar_source(
        self,
        message: TelegramMessage,
    ) -> TelegramUploadSource | None:
        best_photo = self.pick_best_photo(message.photo or [])
        if best_photo is not None:
            return TelegramUploadSource(
                telegram_file_id=best_photo.file_id,
                telegram_file_unique_id=best_photo.file_unique_id,
                filename=f"telegram_avatar_{best_photo.file_id}.jpg",
                content_type="image/jpeg",
            )

        document = message.document
        if document is None:
            return None

        content_type = (document.mime_type or "").strip().lower()
        if not content_type.startswith("image/"):
            return None

        filename = (document.file_name or "").strip() or f"telegram_avatar_{document.file_id}"
        return TelegramUploadSource(
            telegram_file_id=document.file_id,
            telegram_file_unique_id=document.file_unique_id,
            filename=filename,
            content_type=content_type,
        )

    def _extract_resume_source(
        self,
        message: TelegramMessage,
    ) -> TelegramUploadSource | None:
        document = message.document
        if document is None:
            return None

        filename = (document.file_name or "").strip()
        suffix = Path(filename).suffix.lower() if filename else ""
        mime_type = (document.mime_type or "").strip().lower()

        content_type = mime_type or _ALLOWED_RESUME_MIME_BY_EXTENSION.get(suffix)
        if content_type is None:
            return None

        if content_type not in _ALLOWED_RESUME_MIME_BY_EXTENSION.values():
            return None

        safe_filename = filename or f"telegram_resume_{document.file_id}{suffix or '.pdf'}"
        return TelegramUploadSource(
            telegram_file_id=document.file_id,
            telegram_file_unique_id=document.file_unique_id,
            filename=safe_filename,
            content_type=content_type,
        )
