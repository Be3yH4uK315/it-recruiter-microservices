import pytest

from app.application.bot.services import deduplication_service as module_under_test


class FakeProcessedUpdateRepository:
    def __init__(self, _session) -> None:
        self.started_args = None
        self.marked_update_id = None

    async def try_start_processing(self, **kwargs) -> bool:
        self.started_args = kwargs
        return True

    async def mark_processed(self, *, update_id: int) -> None:
        self.marked_update_id = update_id


@pytest.mark.asyncio
async def test_try_start_processing_and_mark_processed(monkeypatch) -> None:
    monkeypatch.setattr(
        module_under_test, "ProcessedUpdateRepository", FakeProcessedUpdateRepository
    )

    service = module_under_test.DeduplicationService(session=object())

    started = await service.try_start_processing(
        update_id=100,
        telegram_user_id=200,
        update_type="message",
    )

    assert started is True
    assert service._repo.started_args == {
        "update_id": 100,
        "telegram_user_id": 200,
        "update_type": "message",
    }

    await service.mark_processed(update_id=100)
    assert service._repo.marked_update_id == 100
