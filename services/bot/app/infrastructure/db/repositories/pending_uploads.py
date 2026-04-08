from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.bot import PendingUploadModel


class PendingUploadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        telegram_user_id: int,
        role_context: str,
        target_service: str,
        target_kind: str,
        owner_id: UUID,
        file_id: UUID,
        filename: str,
        content_type: str,
        telegram_file_id: str | None,
        telegram_file_unique_id: str | None,
    ) -> PendingUploadModel:
        model = PendingUploadModel(
            telegram_user_id=telegram_user_id,
            role_context=role_context,
            target_service=target_service,
            target_kind=target_kind,
            owner_id=owner_id,
            file_id=file_id,
            filename=filename,
            content_type=content_type,
            telegram_file_id=telegram_file_id,
            telegram_file_unique_id=telegram_file_unique_id,
            status="created",
        )
        self._session.add(model)
        await self._session.flush()
        return model

    async def set_status(
        self,
        *,
        model: PendingUploadModel,
        status: str,
        error_message: str | None = None,
    ) -> PendingUploadModel:
        model.status = status
        model.error_message = error_message
        model.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return model

    async def list_non_terminal_for_user(
        self,
        *,
        telegram_user_id: int,
        role_context: str,
        limit: int = 10,
    ) -> list[PendingUploadModel]:
        normalized_limit = max(1, min(limit, 50))
        stmt = (
            select(PendingUploadModel)
            .where(PendingUploadModel.telegram_user_id == telegram_user_id)
            .where(PendingUploadModel.role_context == role_context)
            .where(PendingUploadModel.status.notin_(("linked", "failed")))
            .order_by(PendingUploadModel.updated_at.desc())
            .limit(normalized_limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
