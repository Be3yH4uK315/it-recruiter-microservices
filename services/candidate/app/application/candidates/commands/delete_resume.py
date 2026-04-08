from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import FileGateway
from app.application.common.event_dispatch import dispatch_candidate_events
from app.application.common.uow import UnitOfWork
from app.domain.candidate.errors import CandidateNotFoundError


@dataclass(slots=True, frozen=True)
class DeleteResumeCommand:
    candidate_id: UUID


class DeleteResumeHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        file_gateway: FileGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._file_gateway = file_gateway

    async def __call__(self, command: DeleteResumeCommand) -> None:
        old_file_id: UUID | None = None

        async with self._uow_factory() as uow:
            candidate = await uow.candidates.get_by_id(command.candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate {command.candidate_id} not found")

            old_file_id = candidate.delete_resume()
            if old_file_id is None:
                return

            await uow.candidates.save(candidate)
            await dispatch_candidate_events(uow=uow, candidate=candidate)
            await uow.flush()

        await self._file_gateway.cleanup_file(
            file_id=old_file_id,
            reason="candidate_resume_deleted",
        )
