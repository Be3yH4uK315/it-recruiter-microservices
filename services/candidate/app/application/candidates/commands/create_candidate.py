from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from uuid import uuid4

from app.application.common.event_dispatch import dispatch_candidate_events
from app.application.common.exceptions import ValidationApplicationError
from app.application.common.uow import UnitOfWork
from app.domain.candidate.entities import CandidateProfile
from app.domain.candidate.enums import (
    CandidateStatus,
    ContactsVisibility,
    EnglishLevel,
    SkillKind,
    WorkMode,
)
from app.domain.candidate.errors import CandidateAlreadyExistsError
from app.domain.candidate.value_objects import (
    CandidateSkillVO,
    EducationItemVO,
    ExperienceItemVO,
    ProjectItemVO,
    SalaryRange,
)


@dataclass(slots=True, frozen=True)
class SkillInput:
    skill: str
    kind: SkillKind
    level: int | None = None


@dataclass(slots=True, frozen=True)
class EducationInput:
    level: str
    institution: str
    year: int


@dataclass(slots=True, frozen=True)
class ExperienceInput:
    company: str
    position: str
    start_date: date
    end_date: date | None = None
    responsibilities: str | None = None


@dataclass(slots=True, frozen=True)
class ProjectInput:
    title: str
    description: str | None = None
    links: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class CreateCandidateCommand:
    telegram_id: int
    display_name: str
    headline_role: str
    location: str | None = None
    work_modes: list[WorkMode] = field(default_factory=lambda: [WorkMode.REMOTE])
    contacts_visibility: ContactsVisibility = ContactsVisibility.ON_REQUEST
    contacts: dict[str, str | None] | None = None
    status: CandidateStatus = CandidateStatus.ACTIVE
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = "RUB"
    english_level: EnglishLevel | None = None
    about_me: str | None = None
    skills: list[SkillInput] = field(default_factory=list)
    education: list[EducationInput] = field(default_factory=list)
    experiences: list[ExperienceInput] = field(default_factory=list)
    projects: list[ProjectInput] = field(default_factory=list)


class CreateCandidateHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, command: CreateCandidateCommand) -> CandidateProfile:
        if command.status == CandidateStatus.BLOCKED:
            raise ValidationApplicationError("candidate cannot create profile with blocked status")

        async with self._uow_factory() as uow:
            existing = await uow.candidates.get_by_telegram_id(command.telegram_id)
            if existing is not None:
                raise CandidateAlreadyExistsError(
                    f"candidate with telegram_id={command.telegram_id} already exists"
                )

            candidate = CandidateProfile.create(
                id=uuid4(),
                telegram_id=command.telegram_id,
                display_name=command.display_name,
                headline_role=command.headline_role,
                location=command.location,
                work_modes=list(command.work_modes),
                contacts_visibility=command.contacts_visibility,
                contacts=command.contacts,
                status=command.status,
                english_level=command.english_level,
                about_me=command.about_me,
                salary_range=SalaryRange.from_scalars(
                    salary_min=command.salary_min,
                    salary_max=command.salary_max,
                    currency=command.currency,
                ),
                skills=[
                    CandidateSkillVO(
                        skill=item.skill,
                        kind=item.kind,
                        level=item.level,
                    )
                    for item in command.skills
                ],
                education=[
                    EducationItemVO(
                        level=item.level,
                        institution=item.institution,
                        year=item.year,
                    )
                    for item in command.education
                ],
                experiences=[
                    ExperienceItemVO(
                        company=item.company,
                        position=item.position,
                        start_date=item.start_date,
                        end_date=item.end_date,
                        responsibilities=item.responsibilities,
                    )
                    for item in command.experiences
                ],
                projects=[
                    ProjectItemVO(
                        title=item.title,
                        description=item.description,
                        links=item.links,
                    )
                    for item in command.projects
                ],
                avatar=None,
                resume=None,
            )

            await uow.candidates.add(candidate)
            await dispatch_candidate_events(uow=uow, candidate=candidate)
            await uow.flush()

            return candidate
