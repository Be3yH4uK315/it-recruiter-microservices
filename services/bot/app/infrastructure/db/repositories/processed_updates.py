from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.bot import ProcessedUpdateModel


class ProcessedUpdateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def try_start_processing(
        self,
        *,
        update_id: int,
        telegram_user_id: int | None,
        update_type: str,
    ) -> bool:
        model = ProcessedUpdateModel(
            update_id=update_id,
            telegram_user_id=telegram_user_id,
            update_type=update_type,
            received_at=datetime.now(timezone.utc),
            status="processing",
        )
        self._session.add(model)

        try:
            await self._session.flush()
            return True
        except IntegrityError:
            await self._session.rollback()
            return False

    async def mark_processed(
        self,
        *,
        update_id: int,
    ) -> None:
        model = await self._session.get(ProcessedUpdateModel, update_id)
        if model is None:
            return

        model.status = "processed"
        model.processed_at = datetime.now(timezone.utc)
        await self._session.flush()
