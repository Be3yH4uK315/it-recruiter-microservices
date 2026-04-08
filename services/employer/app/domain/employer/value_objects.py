from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Self
from uuid import UUID

from app.domain.employer.enums import WorkMode
from app.domain.employer.errors import InvalidSearchFilterError


@dataclass(slots=True, frozen=True)
class SalaryRange:
    min_amount: int | None = None
    max_amount: int | None = None
    currency: str = "RUB"

    def __post_init__(self) -> None:
        normalized_currency = (self.currency or "RUB").strip().upper()
        object.__setattr__(self, "currency", normalized_currency)

        if self.min_amount is not None and self.min_amount < 0:
            raise InvalidSearchFilterError("salary_min must be >= 0")
        if self.max_amount is not None and self.max_amount < 0:
            raise InvalidSearchFilterError("salary_max must be >= 0")
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.max_amount < self.min_amount
        ):
            raise InvalidSearchFilterError("salary_max must be >= salary_min")

    @classmethod
    def from_scalars(
        cls,
        *,
        salary_min: int | None,
        salary_max: int | None,
        currency: str | None,
    ) -> Self | None:
        if salary_min is None and salary_max is None and not currency:
            return None

        return cls(
            min_amount=salary_min,
            max_amount=salary_max,
            currency=currency or "RUB",
        )


@dataclass(slots=True, frozen=True)
class SearchSkill:
    skill: str
    level: int | None = None

    def __post_init__(self) -> None:
        normalized = self.skill.strip().lower()
        if not normalized:
            raise InvalidSearchFilterError("skill must not be empty")
        object.__setattr__(self, "skill", normalized)

        if self.level is not None and not (1 <= self.level <= 5):
            raise InvalidSearchFilterError("skill level must be in range 1..5")


@dataclass(slots=True, frozen=True)
class SearchCandidateSnapshot:
    candidate_id: UUID
    display_name: str
    headline_role: str
    experience_years: float
    location: str | None
    skills: tuple[dict[str, Any] | str, ...] = field(default_factory=tuple)
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    english_level: str | None = None
    about_me: str | None = None
    match_score: float = 0.0
    explanation: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class SearchSessionCandidate:
    id: UUID
    session_id: UUID
    rank_position: int
    snapshot: SearchCandidateSnapshot
    is_consumed: bool = False


@dataclass(slots=True, frozen=True)
class SearchFilters:
    role: str
    must_skills: tuple[SearchSkill, ...] = field(default_factory=tuple)
    nice_skills: tuple[SearchSkill, ...] = field(default_factory=tuple)
    experience_min: float | None = None
    experience_max: float | None = None
    location: str | None = None
    work_modes: tuple[WorkMode, ...] = field(default_factory=tuple)
    salary_range: SalaryRange | None = None
    english_level: str | None = None
    exclude_ids: tuple[UUID, ...] = field(default_factory=tuple)
    about_me: str | None = None

    def __post_init__(self) -> None:
        normalized_role = self.role.strip()
        if len(normalized_role) < 2:
            raise InvalidSearchFilterError("role must contain at least 2 characters")
        object.__setattr__(self, "role", normalized_role)

        if self.experience_min is not None and self.experience_min < 0:
            raise InvalidSearchFilterError("experience_min must be >= 0")
        if self.experience_max is not None and self.experience_max < 0:
            raise InvalidSearchFilterError("experience_max must be >= 0")
        if (
            self.experience_min is not None
            and self.experience_max is not None
            and self.experience_max < self.experience_min
        ):
            raise InvalidSearchFilterError("experience_max must be >= experience_min")

        object.__setattr__(self, "must_skills", self._deduplicate_skills(self.must_skills))
        object.__setattr__(self, "nice_skills", self._deduplicate_skills(self.nice_skills))
        object.__setattr__(self, "work_modes", self._deduplicate_work_modes(self.work_modes))
        object.__setattr__(self, "location", self._normalize_optional_text(self.location))
        object.__setattr__(self, "english_level", self._normalize_optional_text(self.english_level))
        object.__setattr__(self, "about_me", self._normalize_optional_text(self.about_me))
        object.__setattr__(self, "exclude_ids", self._deduplicate_ids(self.exclude_ids))

    @staticmethod
    def _deduplicate_skills(items: tuple[SearchSkill, ...]) -> tuple[SearchSkill, ...]:
        seen: dict[str, SearchSkill] = {}
        for item in items:
            if item.skill not in seen:
                seen[item.skill] = item
        return tuple(seen.values())

    @staticmethod
    def _deduplicate_work_modes(items: tuple[WorkMode, ...]) -> tuple[WorkMode, ...]:
        seen: set[WorkMode] = set()
        result: list[WorkMode] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return tuple(result)

    @staticmethod
    def _deduplicate_ids(items: tuple[UUID, ...]) -> tuple[UUID, ...]:
        seen: set[UUID] = set()
        result: list[UUID] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return tuple(result)

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def merge_exclude_ids(self, *groups: list[UUID] | tuple[UUID, ...]) -> "SearchFilters":
        merged: list[UUID] = list(self.exclude_ids)
        seen = set(merged)

        for group in groups:
            for item in group:
                if item not in seen:
                    merged.append(item)
                    seen.add(item)

        return SearchFilters(
            role=self.role,
            must_skills=self.must_skills,
            nice_skills=self.nice_skills,
            experience_min=self.experience_min,
            experience_max=self.experience_max,
            location=self.location,
            work_modes=self.work_modes,
            salary_range=self.salary_range,
            english_level=self.english_level,
            exclude_ids=tuple(merged),
            about_me=self.about_me,
        )

    def to_primitives(self) -> dict:
        salary_min = self.salary_range.min_amount if self.salary_range else None
        salary_max = self.salary_range.max_amount if self.salary_range else None
        currency = self.salary_range.currency if self.salary_range else None

        return {
            "role": self.role,
            "must_skills": [
                {"skill": item.skill, "level": item.level} for item in self.must_skills
            ],
            "nice_skills": [
                {"skill": item.skill, "level": item.level} for item in self.nice_skills
            ],
            "experience_min": self.experience_min,
            "experience_max": self.experience_max,
            "location": self.location,
            "work_modes": [item.value for item in self.work_modes],
            "salary_min": salary_min,
            "salary_max": salary_max,
            "currency": currency,
            "english_level": self.english_level,
            "exclude_ids": [str(item) for item in self.exclude_ids],
            "about_me": self.about_me,
        }


@dataclass(slots=True, frozen=True)
class EmployerContacts:
    email: str | None = None
    telegram: str | None = None
    phone: str | None = None
    website: str | None = None

    @classmethod
    def from_dict(cls, value: dict | None) -> Self | None:
        if not value:
            return None

        return cls(
            email=cls._normalize_optional_text(value.get("email")),
            telegram=cls._normalize_optional_text(value.get("telegram")),
            phone=cls._normalize_optional_text(value.get("phone")),
            website=cls._normalize_optional_text(value.get("website")),
        )

    @staticmethod
    def _normalize_optional_text(value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "email": self.email,
            "telegram": self.telegram,
            "phone": self.phone,
            "website": self.website,
        }
