from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.uow import UnitOfWork
from app.domain.employer.entities import SearchDecision
from app.domain.employer.enums import DecisionType, SearchStatus
from app.domain.employer.errors import (
    SearchSessionClosedError,
    SearchSessionNotFoundError,
    SearchSessionPausedError,
)


@dataclass(slots=True, frozen=True)
class SubmitDecisionCommand:
    session_id: UUID
    candidate_id: UUID
    decision: DecisionType
    note: str | None = None


class SubmitDecisionHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, command: SubmitDecisionCommand) -> SearchDecision:
        async with self._uow_factory() as uow:
            session = await uow.searches.get_by_id(command.session_id)
            if session is None:
                raise SearchSessionNotFoundError(f"search session {command.session_id} not found")

            if session.status == SearchStatus.CLOSED:
                raise SearchSessionClosedError("search session is closed")

            if session.status == SearchStatus.PAUSED:
                raise SearchSessionPausedError("search session is paused")

            decision = session.submit_decision(
                candidate_id=command.candidate_id,
                decision=command.decision,
                note=command.note,
            )

            await uow.searches.upsert_decision(session.id, decision)
            await uow.searches.mark_pool_candidate_consumed(
                session_id=session.id,
                candidate_id=command.candidate_id,
            )
            await uow.searches.save(session)
            await uow.flush()

            return decision
