from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Final
from uuid import UUID

from app.domain.candidate.enums import (
    CandidateStatus,
    ContactsVisibility,
    EnglishLevel,
    WorkMode,
)
from app.domain.candidate.errors import CandidateDomainError, CannotUnblockYourselfError
from app.domain.candidate.value_objects import (
    AvatarRef,
    CandidateSkillVO,
    EducationItemVO,
    ExperienceItemVO,
    ProjectItemVO,
    ResumeRef,
    SalaryRange,
)
from app.domain.common.events import DomainEvent

UNSET: Final = object()
_ALLOWED_CONTACT_KEYS: Final[set[str]] = {"telegram", "email", "phone"}


@dataclass(slots=True, frozen=True)
class CandidateCreated(DomainEvent):
    candidate_id: UUID | None = None
    telegram_id: int | None = None


@dataclass(slots=True, frozen=True)
class CandidateProfileUpdated(DomainEvent):
    candidate_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class CandidateAvatarReplaced(DomainEvent):
    candidate_id: UUID | None = None
    new_file_id: UUID | None = None
    old_file_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class CandidateAvatarDeleted(DomainEvent):
    candidate_id: UUID | None = None
    file_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class CandidateResumeReplaced(DomainEvent):
    candidate_id: UUID | None = None
    new_file_id: UUID | None = None
    old_file_id: UUID | None = None


@dataclass(slots=True, frozen=True)
class CandidateResumeDeleted(DomainEvent):
    candidate_id: UUID | None = None
    file_id: UUID | None = None


@dataclass(slots=True)
class CandidateProfile:
    id: UUID
    telegram_id: int
    display_name: str
    headline_role: str
    location: str | None
    work_modes: list[WorkMode]
    contacts_visibility: ContactsVisibility
    contacts: dict[str, str | None] | None
    status: CandidateStatus
    english_level: EnglishLevel | None
    about_me: str | None
    salary_range: SalaryRange | None = None
    skills: list[CandidateSkillVO] = field(default_factory=list)
    education: list[EducationItemVO] = field(default_factory=list)
    experiences: list[ExperienceItemVO] = field(default_factory=list)
    projects: list[ProjectItemVO] = field(default_factory=list)
    avatar: AvatarRef | None = None
    resume: ResumeRef | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version_id: int = 1
    _events: list[DomainEvent] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        telegram_id: int,
        display_name: str,
        headline_role: str,
        location: str | None,
        work_modes: list[WorkMode],
        contacts_visibility: ContactsVisibility,
        contacts: dict[str, str | None] | None,
        status: CandidateStatus,
        english_level: EnglishLevel | None,
        about_me: str | None,
        salary_range: SalaryRange | None,
        skills: list[CandidateSkillVO],
        education: list[EducationItemVO],
        experiences: list[ExperienceItemVO],
        projects: list[ProjectItemVO],
        avatar: AvatarRef | None = None,
        resume: ResumeRef | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version_id: int = 1,
    ) -> "CandidateProfile":
        candidate = cls(
            id=id,
            telegram_id=telegram_id,
            display_name=cls._normalize_required_text(display_name, field_name="display_name"),
            headline_role=cls._normalize_required_text(headline_role, field_name="headline_role"),
            location=cls._normalize_optional_text(location),
            work_modes=cls._normalize_work_modes(work_modes),
            contacts_visibility=contacts_visibility,
            contacts=cls._normalize_contacts(contacts),
            status=status,
            english_level=english_level,
            about_me=cls._normalize_optional_text(about_me),
            salary_range=salary_range,
            skills=list(skills),
            education=list(education),
            experiences=list(experiences),
            projects=list(projects),
            avatar=avatar,
            resume=resume,
            created_at=created_at or datetime.now(timezone.utc),
            updated_at=updated_at or datetime.now(timezone.utc),
            version_id=version_id,
        )
        candidate._validate_invariants()
        candidate._events.append(
            CandidateCreated(
                candidate_id=candidate.id,
                telegram_id=candidate.telegram_id,
            )
        )
        return candidate

    def update_profile(
        self,
        *,
        display_name: str | None | object = UNSET,
        headline_role: str | None | object = UNSET,
        location: str | None | object = UNSET,
        work_modes: list[WorkMode] | object = UNSET,
        contacts_visibility: ContactsVisibility | object = UNSET,
        contacts: dict[str, str | None] | None | object = UNSET,
        status: CandidateStatus | object = UNSET,
        english_level: EnglishLevel | None | object = UNSET,
        about_me: str | None | object = UNSET,
        salary_range: SalaryRange | None | object = UNSET,
        skills: list[CandidateSkillVO] | object = UNSET,
        education: list[EducationItemVO] | object = UNSET,
        experiences: list[ExperienceItemVO] | object = UNSET,
        projects: list[ProjectItemVO] | object = UNSET,
    ) -> None:
        changed = False

        if display_name is not UNSET:
            normalized = self._normalize_required_text(display_name, field_name="display_name")
            if normalized != self.display_name:
                self.display_name = normalized
                changed = True

        if headline_role is not UNSET:
            normalized = self._normalize_required_text(
                headline_role,
                field_name="headline_role",
            )
            if normalized != self.headline_role:
                self.headline_role = normalized
                changed = True

        if location is not UNSET:
            normalized = self._normalize_optional_text(location)
            if normalized != self.location:
                self.location = normalized
                changed = True

        if work_modes is not UNSET:
            normalized = self._normalize_work_modes(work_modes)
            if normalized != self.work_modes:
                self.work_modes = normalized
                changed = True

        if contacts_visibility is not UNSET and contacts_visibility != self.contacts_visibility:
            self.contacts_visibility = contacts_visibility
            changed = True

        if contacts is not UNSET:
            normalized = self._normalize_contacts(contacts)
            if normalized != self.contacts:
                self.contacts = normalized
                changed = True

        if status is not UNSET:
            if self.status == CandidateStatus.BLOCKED and status != CandidateStatus.BLOCKED:
                raise CannotUnblockYourselfError("candidate cannot change status while blocked")
            if status != self.status:
                self.status = status
                changed = True

        if english_level is not UNSET and english_level != self.english_level:
            self.english_level = english_level
            changed = True

        if about_me is not UNSET:
            normalized = self._normalize_optional_text(about_me)
            if normalized != self.about_me:
                self.about_me = normalized
                changed = True

        if salary_range is not UNSET and salary_range != self.salary_range:
            self.salary_range = salary_range
            changed = True

        if skills is not UNSET and skills != self.skills:
            self.skills = list(skills)
            changed = True

        if education is not UNSET and education != self.education:
            self.education = list(education)
            changed = True

        if experiences is not UNSET and experiences != self.experiences:
            self.experiences = list(experiences)
            changed = True

        if projects is not UNSET and projects != self.projects:
            self.projects = list(projects)
            changed = True

        if changed:
            self._validate_invariants()
            self.updated_at = datetime.now(timezone.utc)
            self._events.append(
                CandidateProfileUpdated(
                    candidate_id=self.id,
                )
            )

    def replace_avatar(self, *, file_id: UUID) -> UUID | None:
        old_file_id = self.avatar.file_id if self.avatar is not None else None
        self.avatar = AvatarRef(file_id=file_id)
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            CandidateAvatarReplaced(
                candidate_id=self.id,
                new_file_id=file_id,
                old_file_id=old_file_id,
            )
        )
        return old_file_id

    def delete_avatar(self) -> UUID | None:
        if self.avatar is None:
            return None

        old_file_id = self.avatar.file_id
        self.avatar = None
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            CandidateAvatarDeleted(
                candidate_id=self.id,
                file_id=old_file_id,
            )
        )
        return old_file_id

    def replace_resume(self, *, file_id: UUID) -> UUID | None:
        old_file_id = self.resume.file_id if self.resume is not None else None
        self.resume = ResumeRef(file_id=file_id)
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            CandidateResumeReplaced(
                candidate_id=self.id,
                new_file_id=file_id,
                old_file_id=old_file_id,
            )
        )
        return old_file_id

    def delete_resume(self) -> UUID | None:
        if self.resume is None:
            return None

        old_file_id = self.resume.file_id
        self.resume = None
        self.updated_at = datetime.now(timezone.utc)
        self._events.append(
            CandidateResumeDeleted(
                candidate_id=self.id,
                file_id=old_file_id,
            )
        )
        return old_file_id

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def _validate_invariants(self) -> None:
        if self.telegram_id <= 0:
            raise CandidateDomainError("telegram_id must be positive")

        if not self.display_name:
            raise CandidateDomainError("display_name must not be empty")

        if not self.headline_role:
            raise CandidateDomainError("headline_role must not be empty")

        if self.contacts is None or not self.contacts.get("telegram"):
            raise CandidateDomainError("contacts.telegram is required")

    @staticmethod
    def _normalize_required_text(value: str | None, *, field_name: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise CandidateDomainError(f"{field_name} must not be empty")
        return normalized

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @classmethod
    def _normalize_contacts(
        cls,
        value: dict[str, str | None] | None,
    ) -> dict[str, str | None] | None:
        if value is None:
            return None

        result: dict[str, str | None] = {}
        for key, item in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key not in _ALLOWED_CONTACT_KEYS:
                continue

            if item is None:
                result[normalized_key] = None
                continue

            normalized_value = str(item).strip()
            result[normalized_key] = normalized_value or None

        return result or None

    @staticmethod
    def _normalize_work_modes(value: list[WorkMode]) -> list[WorkMode]:
        seen: set[WorkMode] = set()
        result: list[WorkMode] = []

        for item in value:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)

        return result
