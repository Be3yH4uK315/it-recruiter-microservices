from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Final
from uuid import UUID

from app.application.common.event_dispatch import dispatch_candidate_events
from app.application.common.exceptions import ValidationApplicationError
from app.application.common.uow import UnitOfWork
from app.domain.candidate.entities import UNSET, CandidateProfile
from app.domain.candidate.enums import (
    CandidateStatus,
    ContactsVisibility,
    EnglishLevel,
    SkillKind,
    WorkMode,
)
from app.domain.candidate.errors import CandidateNotFoundError
from app.domain.candidate.value_objects import (
    CandidateSkillVO,
    EducationItemVO,
    ExperienceItemVO,
    ProjectItemVO,
    SalaryRange,
)

UNSET_VALUE: Final = UNSET


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
class UpdateCandidateCommand:
    candidate_id: UUID
    display_name: str | None | object = UNSET_VALUE
    headline_role: str | None | object = UNSET_VALUE
    location: str | None | object = UNSET_VALUE
    work_modes: list[WorkMode] | object = UNSET_VALUE
    contacts_visibility: ContactsVisibility | object = UNSET_VALUE
    contacts: dict[str, str | None] | None | object = UNSET_VALUE
    status: CandidateStatus | object = UNSET_VALUE
    salary_min: int | None | object = UNSET_VALUE
    salary_max: int | None | object = UNSET_VALUE
    currency: str | None | object = UNSET_VALUE
    english_level: EnglishLevel | None | object = UNSET_VALUE
    about_me: str | None | object = UNSET_VALUE
    skills: list[SkillInput] | object = UNSET_VALUE
    education: list[EducationInput] | object = UNSET_VALUE
    experiences: list[ExperienceInput] | object = UNSET_VALUE
    projects: list[ProjectInput] | object = UNSET_VALUE


class UpdateCandidateHandler:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def __call__(self, command: UpdateCandidateCommand) -> CandidateProfile:
        if command.status is not UNSET_VALUE and command.status == CandidateStatus.BLOCKED:
            raise ValidationApplicationError("candidate cannot set blocked status")

        async with self._uow_factory() as uow:
            candidate = await uow.candidates.get_by_id(command.candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate {command.candidate_id} not found")

            candidate.update_profile(
                display_name=command.display_name,
                headline_role=command.headline_role,
                location=command.location,
                work_modes=command.work_modes,
                contacts_visibility=command.contacts_visibility,
                contacts=command.contacts,
                status=command.status,
                english_level=command.english_level,
                about_me=command.about_me,
                salary_range=self._build_salary_range(command, candidate),
                skills=self._build_skills(command),
                education=self._build_education(command),
                experiences=self._build_experiences(command),
                projects=self._build_projects(command),
            )

            await uow.candidates.save(candidate)
            await dispatch_candidate_events(uow=uow, candidate=candidate)
            await uow.flush()

            return candidate

    @staticmethod
    def _build_salary_range(
        command: UpdateCandidateCommand,
        candidate: CandidateProfile,
    ) -> SalaryRange | None | object:
        if (
            command.salary_min is UNSET_VALUE
            and command.salary_max is UNSET_VALUE
            and command.currency is UNSET_VALUE
        ):
            return UNSET_VALUE

        current = candidate.salary_range
        salary_min = current.min_amount if current is not None else None
        salary_max = current.max_amount if current is not None else None
        currency = current.currency if current is not None else None

        if command.salary_min is not UNSET_VALUE:
            salary_min = command.salary_min
        if command.salary_max is not UNSET_VALUE:
            salary_max = command.salary_max
        if command.currency is not UNSET_VALUE:
            currency = command.currency

        return SalaryRange.from_scalars(
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
        )

    @staticmethod
    def _build_skills(command: UpdateCandidateCommand) -> list[CandidateSkillVO] | object:
        if command.skills is UNSET_VALUE:
            return UNSET_VALUE

        return [
            CandidateSkillVO(
                skill=item.skill,
                kind=item.kind,
                level=item.level,
            )
            for item in command.skills
        ]

    @staticmethod
    def _build_education(command: UpdateCandidateCommand) -> list[EducationItemVO] | object:
        if command.education is UNSET_VALUE:
            return UNSET_VALUE

        return [
            EducationItemVO(
                level=item.level,
                institution=item.institution,
                year=item.year,
            )
            for item in command.education
        ]

    @staticmethod
    def _build_experiences(command: UpdateCandidateCommand) -> list[ExperienceItemVO] | object:
        if command.experiences is UNSET_VALUE:
            return UNSET_VALUE

        return [
            ExperienceItemVO(
                company=item.company,
                position=item.position,
                start_date=item.start_date,
                end_date=item.end_date,
                responsibilities=item.responsibilities,
            )
            for item in command.experiences
        ]

    @staticmethod
    def _build_projects(command: UpdateCandidateCommand) -> list[ProjectItemVO] | object:
        if command.projects is UNSET_VALUE:
            return UNSET_VALUE

        return [
            ProjectItemVO(
                title=item.title,
                description=item.description,
                links=item.links,
            )
            for item in command.projects
        ]
