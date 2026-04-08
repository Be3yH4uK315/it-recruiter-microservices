from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import FileGateway
from app.application.common.event_dispatch import dispatch_candidate_events
from app.application.common.uow import UnitOfWork
from app.domain.candidate.errors import (
    CandidateNotFoundError,
    InvalidCandidateFileError,
)


@dataclass(slots=True, frozen=True)
class ReplaceAvatarCommand:
    candidate_id: UUID
    file_id: UUID


class ReplaceAvatarHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        file_gateway: FileGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._file_gateway = file_gateway

    async def __call__(self, command: ReplaceAvatarCommand) -> None:
        async with self._uow_factory() as uow:
            candidate = await uow.candidates.get_by_id(command.candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate {command.candidate_id} not found")

        file_metadata = await self._file_gateway.complete_file_upload(file_id=command.file_id)

        if file_metadata.owner_service != "candidate-service":
            raise InvalidCandidateFileError("file owner_service is invalid")
        if file_metadata.owner_id != command.candidate_id:
            raise InvalidCandidateFileError("file owner_id does not match candidate")
        if file_metadata.category != "candidate_avatar":
            raise InvalidCandidateFileError("file category is invalid for avatar")
        if file_metadata.status != "active":
            raise InvalidCandidateFileError("file is not active")

        old_file_id: UUID | None = None

        async with self._uow_factory() as uow:
            candidate = await uow.candidates.get_by_id(command.candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate {command.candidate_id} not found")

            old_file_id = candidate.replace_avatar(file_id=command.file_id)

            await uow.candidates.save(candidate)
            await dispatch_candidate_events(uow=uow, candidate=candidate)
            await uow.flush()

        if old_file_id is not None and old_file_id != command.file_id:
            await self._file_gateway.cleanup_file(
                file_id=old_file_id,
                reason="candidate_avatar_replaced",
            )
