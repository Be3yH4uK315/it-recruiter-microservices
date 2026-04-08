from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.domain.candidate.enums import (
    CandidateStatus,
    ContactsVisibility,
    EnglishLevel,
    SkillKind,
    WorkMode,
)


@dataclass(slots=True, frozen=True)
class CandidateSkillView:
    skill: str
    kind: SkillKind
    level: int | None = None


@dataclass(slots=True, frozen=True)
class CandidateEducationView:
    level: str
    institution: str
    year: int


@dataclass(slots=True, frozen=True)
class CandidateExperienceView:
    company: str
    position: str
    start_date: date
    end_date: date | None = None
    responsibilities: str | None = None


@dataclass(slots=True, frozen=True)
class CandidateProjectView:
    title: str
    description: str | None = None
    links: list[str] | None = None


@dataclass(slots=True, frozen=True)
class CandidateProfileView:
    id: UUID
    telegram_id: int
    display_name: str
    headline_role: str
    location: str | None
    work_modes: list[WorkMode]
    experience_years: float
    contacts_visibility: ContactsVisibility
    contacts: dict[str, str | None] | None
    status: CandidateStatus
    english_level: EnglishLevel | None
    about_me: str | None
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    skills: list[CandidateSkillView]
    education: list[CandidateEducationView]
    experiences: list[CandidateExperienceView]
    projects: list[CandidateProjectView]
    avatar_file_id: UUID | None
    avatar_download_url: str | None
    resume_file_id: UUID | None
    resume_download_url: str | None
    created_at: datetime | None
    updated_at: datetime | None
    version_id: int


@dataclass(slots=True, frozen=True)
class CandidateEmployerView:
    id: UUID
    display_name: str
    headline_role: str
    location: str | None
    work_modes: list[WorkMode]
    experience_years: float
    contacts_visibility: ContactsVisibility
    contacts: dict[str, str | None] | None
    can_view_contacts: bool
    status: CandidateStatus
    english_level: EnglishLevel | None
    about_me: str | None
    salary_min: int | None
    salary_max: int | None
    currency: str | None
    skills: list[CandidateSkillView]
    education: list[CandidateEducationView]
    experiences: list[CandidateExperienceView]
    projects: list[CandidateProjectView]
    avatar_file_id: UUID | None
    avatar_download_url: str | None
    resume_file_id: UUID | None
    resume_download_url: str | None
    created_at: datetime | None
    updated_at: datetime | None
    version_id: int
