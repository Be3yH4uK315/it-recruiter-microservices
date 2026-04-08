from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.application.common.event_dispatch import dispatch_search_session_events
from app.application.common.uow import UnitOfWork
from app.domain.employer.entities import SearchSession
from app.domain.employer.enums import WorkMode
from app.domain.employer.errors import EmployerNotFoundError
from app.domain.employer.value_objects import SalaryRange, SearchFilters, SearchSkill


@dataclass(slots=True, frozen=True)
class SkillInput:
    skill: str
    level: int | None = None


@dataclass(slots=True, frozen=True)
class CreateSearchSessionCommand:
    employer_id: UUID
    title: str
    role: str
    must_skills: list[SkillInput] = field(default_factory=list)
    nice_skills: list[SkillInput] = field(default_factory=list)
    experience_min: float | None = None
    experience_max: float | None = None
    location: str | None = None
    work_modes: list[WorkMode] = field(default_factory=list)
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = "RUB"
    english_level: str | None = None
    exclude_ids: list[UUID] = field(default_factory=list)
    about_me: str | None = None


class CreateSearchSessionHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, command: CreateSearchSessionCommand) -> SearchSession:
        async with self._uow_factory() as uow:
            employer = await uow.employers.get_by_id(command.employer_id)
            if employer is None:
                raise EmployerNotFoundError(f"employer {command.employer_id} not found")

            filters = SearchFilters(
                role=command.role,
                must_skills=tuple(
                    SearchSkill(skill=item.skill, level=item.level) for item in command.must_skills
                ),
                nice_skills=tuple(
                    SearchSkill(skill=item.skill, level=item.level) for item in command.nice_skills
                ),
                experience_min=command.experience_min,
                experience_max=command.experience_max,
                location=command.location,
                work_modes=tuple(command.work_modes),
                salary_range=SalaryRange.from_scalars(
                    salary_min=command.salary_min,
                    salary_max=command.salary_max,
                    currency=command.currency,
                ),
                english_level=command.english_level,
                exclude_ids=tuple(command.exclude_ids),
                about_me=command.about_me,
            )

            session = SearchSession.create(
                id=uuid4(),
                employer_id=command.employer_id,
                title=command.title,
                filters=filters,
            )

            await uow.searches.add(session)
            await dispatch_search_session_events(
                uow=uow,
                employer=employer,
                search_session=session,
            )
            await uow.flush()

            return session
