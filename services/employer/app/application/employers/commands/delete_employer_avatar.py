from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.common.contracts import FileGateway
from app.application.common.event_dispatch import dispatch_employer_events
from app.application.common.uow import UnitOfWork
from app.domain.employer.errors import EmployerNotFoundError


@dataclass(slots=True, frozen=True)
class DeleteEmployerAvatarCommand:
    employer_id: UUID


class DeleteEmployerAvatarHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        file_gateway: FileGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._file_gateway = file_gateway

    async def __call__(self, command: DeleteEmployerAvatarCommand) -> None:
        old_file_id: UUID | None = None

        async with self._uow_factory() as uow:
            employer = await uow.employers.get_by_id(command.employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {command.employer_id} not found")

            old_file_id = employer.delete_avatar()

            await uow.employers.save(employer)
            await dispatch_employer_events(uow=uow, employer=employer)
            await uow.flush()

        if old_file_id is not None:
            await self._file_gateway.cleanup_file(
                file_id=old_file_id,
                reason="employer_avatar_deleted",
            )
