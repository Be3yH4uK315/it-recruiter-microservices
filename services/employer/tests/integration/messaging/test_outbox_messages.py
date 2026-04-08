from __future__ import annotations

from sqlalchemy import select

from app.infrastructure.db.models.employer import OutboxMessage
from app.infrastructure.db.repositories.outbox import SqlAlchemyOutboxRepository


async def test_outbox_message_created(session_factory) -> None:
    async with session_factory() as session:
        repo = SqlAlchemyOutboxRepository(session)
        await repo.publish(
            routing_key="employer.created",
            payload={"employer_id": "123"},
        )
        await session.commit()

    async with session_factory() as session:
        result = await session.execute(select(OutboxMessage))
        items = list(result.scalars().all())

    assert len(items) == 1
    assert items[0].routing_key == "employer.created"
    assert items[0].message_body == {"employer_id": "123"}
    assert items[0].status == "pending"
