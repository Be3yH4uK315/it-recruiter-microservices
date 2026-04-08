from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.repositories.processed_updates import ProcessedUpdateRepository


class DeduplicationService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ProcessedUpdateRepository(session)

    async def try_start_processing(
        self,
        *,
        update_id: int,
        telegram_user_id: int | None,
        update_type: str,
    ) -> bool:
        return await self._repo.try_start_processing(
            update_id=update_id,
            telegram_user_id=telegram_user_id,
            update_type=update_type,
        )

    async def mark_processed(self, *, update_id: int) -> None:
        await self._repo.mark_processed(update_id=update_id)
