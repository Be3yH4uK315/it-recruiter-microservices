from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from app.application.common.event_dispatch import dispatch_employer_events
from app.application.common.uow import UnitOfWork
from app.domain.employer.entities import UNSET, EmployerProfile
from app.domain.employer.errors import EmployerNotFoundError
from app.domain.employer.value_objects import EmployerContacts

UNSET_VALUE: Final = UNSET


@dataclass(slots=True, frozen=True)
class UpdateEmployerCommand:
    employer_id: UUID
    company: str | None | object = UNSET_VALUE
    contacts: dict[str, str | None] | None | object = UNSET_VALUE


class UpdateEmployerHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, command: UpdateEmployerCommand) -> EmployerProfile:
        async with self._uow_factory() as uow:
            employer = await uow.employers.get_by_id(command.employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {command.employer_id} not found")

            employer.update_profile(
                company=command.company,
                contacts=self._build_contacts(command),
            )

            await uow.employers.save(employer)
            await dispatch_employer_events(uow=uow, employer=employer)
            await uow.flush()
            return employer

    @staticmethod
    def _build_contacts(
        command: UpdateEmployerCommand,
    ) -> EmployerContacts | None | object:
        if command.contacts is UNSET_VALUE:
            return UNSET_VALUE
        return EmployerContacts.from_dict(command.contacts)
