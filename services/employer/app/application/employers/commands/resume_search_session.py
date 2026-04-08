from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.event_dispatch import dispatch_search_session_events
from app.application.common.uow import UnitOfWork
from app.domain.employer.entities import SearchSession
from app.domain.employer.errors import EmployerNotFoundError, SearchSessionNotFoundError


@dataclass(slots=True, frozen=True)
class ResumeSearchSessionCommand:
    session_id: UUID


class ResumeSearchSessionHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, command: ResumeSearchSessionCommand) -> SearchSession:
        async with self._uow_factory() as uow:
            session = await uow.searches.get_by_id(command.session_id)
            if session is None:
                raise SearchSessionNotFoundError(f"search session {command.session_id} not found")

            employer = await uow.employers.get_by_id(session.employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {session.employer_id} not found")

            session.activate()
            await uow.searches.save(session)
            await dispatch_search_session_events(
                uow=uow,
                employer=employer,
                search_session=session,
            )
            await uow.flush()
            return session
