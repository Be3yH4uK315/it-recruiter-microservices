from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from app.application.common.event_dispatch import dispatch_employer_events
from app.application.common.uow import UnitOfWork
from app.domain.employer.entities import EmployerProfile
from app.domain.employer.errors import EmployerAlreadyExistsError
from app.domain.employer.value_objects import EmployerContacts


@dataclass(slots=True, frozen=True)
class CreateEmployerCommand:
    telegram_id: int
    company: str | None = None
    contacts: dict[str, str | None] | None = None


class CreateEmployerHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, command: CreateEmployerCommand) -> EmployerProfile:
        async with self._uow_factory() as uow:
            existing = await uow.employers.get_by_telegram_id(command.telegram_id)
            if existing is not None:
                raise EmployerAlreadyExistsError(
                    f"employer with telegram_id={command.telegram_id} already exists"
                )

            employer = EmployerProfile.create(
                id=uuid4(),
                telegram_id=command.telegram_id,
                company=command.company,
                contacts=EmployerContacts.from_dict(command.contacts),
                avatar_file_id=None,
                document_file_id=None,
            )

            await uow.employers.add(employer)
            await dispatch_employer_events(uow=uow, employer=employer)
            await uow.flush()

            return employer
