from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.models.auth import OutboxMessageModel
from app.infrastructure.db.repositories.outbox import SqlAlchemyOutboxRepository


@pytest.mark.asyncio
async def test_outbox_publish_creates_pending_message(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SqlAlchemyOutboxRepository(session)

        await repo.publish(
            routing_key="auth.user.created",
            payload={"user_id": "123", "role": "employer"},
        )
        await session.commit()

    async with session_factory() as session:
        items = (await session.execute(OutboxMessageModel.__table__.select())).all()

        assert len(items) == 1


@pytest.mark.asyncio
async def test_outbox_get_pending_batch_returns_only_pending(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SqlAlchemyOutboxRepository(session)

        await repo.publish(routing_key="one", payload={"value": 1})
        await repo.publish(routing_key="two", payload={"value": 2})
        await session.flush()

        pending = await repo.get_pending_batch(limit=10)
        pending[0].status = "published"

        await session.commit()

    async with session_factory() as session:
        repo = SqlAlchemyOutboxRepository(session)
        batch = await repo.get_pending_batch(limit=10)

        assert len(batch) == 1
        assert batch[0].routing_key == "two"


@pytest.mark.asyncio
async def test_outbox_mark_published_updates_message(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SqlAlchemyOutboxRepository(session)
        await repo.publish(routing_key="auth.session.issued", payload={"x": 1})
        await session.flush()

        batch = await repo.get_pending_batch(limit=10)
        assert len(batch) == 1

        message = batch[0]
        await repo.mark_published(message)
        await session.commit()

    async with session_factory() as session:
        repo = SqlAlchemyOutboxRepository(session)
        batch = await repo.get_pending_batch(limit=10)

        assert batch == []

        result = await session.get(OutboxMessageModel, message.id)
        assert result is not None
        assert result.status == "published"
        assert result.processed_at is not None
        assert result.error_log is None


@pytest.mark.asyncio
async def test_outbox_mark_failed_keeps_pending_before_max_retries(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SqlAlchemyOutboxRepository(session)
        await repo.publish(routing_key="auth.session.revoked", payload={"x": 1})
        await session.flush()

        batch = await repo.get_pending_batch(limit=10)
        message = batch[0]

        await repo.mark_failed(
            message,
            error="temporary error",
            max_retries=3,
        )
        await session.commit()

    async with session_factory() as session:
        result = await session.get(OutboxMessageModel, message.id)

        assert result is not None
        assert result.status == "pending"
        assert result.retry_count == 1
        assert result.error_log == "temporary error"


@pytest.mark.asyncio
async def test_outbox_mark_failed_sets_failed_on_max_retries(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = SqlAlchemyOutboxRepository(session)
        await repo.publish(routing_key="auth.session.revoked", payload={"x": 1})
        await session.flush()

        batch = await repo.get_pending_batch(limit=10)
        message = batch[0]

        message.retry_count = 2
        await repo.mark_failed(
            message,
            error="fatal error",
            max_retries=3,
        )
        await session.commit()

    async with session_factory() as session:
        result = await session.get(OutboxMessageModel, message.id)

        assert result is not None
        assert result.status == "failed"
        assert result.retry_count == 3
        assert result.error_log == "fatal error"
