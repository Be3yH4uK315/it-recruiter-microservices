from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Self
from urllib.parse import urlparse
from uuid import UUID

from app.domain.candidate.enums import SkillKind
from app.domain.candidate.errors import CandidateDomainError, InvalidSalaryRangeError


@dataclass(slots=True, frozen=True)
class SalaryRange:
    min_amount: int | None = None
    max_amount: int | None = None
    currency: str = "RUB"

    def __post_init__(self) -> None:
        normalized_currency = (self.currency or "RUB").strip().upper()
        object.__setattr__(self, "currency", normalized_currency)

        if self.min_amount is not None and self.min_amount < 0:
            raise InvalidSalaryRangeError("salary_min must be >= 0")
        if self.max_amount is not None and self.max_amount < 0:
            raise InvalidSalaryRangeError("salary_max must be >= 0")
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.max_amount < self.min_amount
        ):
            raise InvalidSalaryRangeError("salary_max must be >= salary_min")

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
class CandidateSkillVO:
    skill: str
    kind: SkillKind
    level: int | None = None

    def __post_init__(self) -> None:
        normalized = self.skill.strip()
        object.__setattr__(self, "skill", normalized)

        if not normalized:
            raise CandidateDomainError("skill must not be empty")

        if self.level is not None and not (1 <= self.level <= 5):
            raise CandidateDomainError("skill level must be in range 1..5")


@dataclass(slots=True, frozen=True)
class EducationItemVO:
    level: str
    institution: str
    year: int

    def __post_init__(self) -> None:
        normalized_level = self.level.strip()
        normalized_institution = self.institution.strip()

        object.__setattr__(self, "level", normalized_level)
        object.__setattr__(self, "institution", normalized_institution)

        if not normalized_level:
            raise CandidateDomainError("education level must not be empty")
        if not normalized_institution:
            raise CandidateDomainError("education institution must not be empty")
        if not (1950 <= self.year <= 2100):
            raise CandidateDomainError("education year must be in range 1950..2100")


@dataclass(slots=True, frozen=True)
class ExperienceItemVO:
    company: str
    position: str
    start_date: date
    end_date: date | None = None
    responsibilities: str | None = None

    def __post_init__(self) -> None:
        normalized_company = self.company.strip()
        normalized_position = self.position.strip()
        normalized_responsibilities = (
            self.responsibilities.strip() if self.responsibilities is not None else None
        )

        object.__setattr__(self, "company", normalized_company)
        object.__setattr__(self, "position", normalized_position)
        object.__setattr__(self, "responsibilities", normalized_responsibilities or None)

        if not normalized_company:
            raise CandidateDomainError("experience company must not be empty")
        if not normalized_position:
            raise CandidateDomainError("experience position must not be empty")
        if self.end_date is not None and self.end_date < self.start_date:
            raise CandidateDomainError("experience end_date must be >= start_date")


@dataclass(slots=True, frozen=True)
class ProjectItemVO:
    title: str
    description: str | None = None
    links: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        normalized_title = self.title.strip()
        normalized_description = self.description.strip() if self.description is not None else None
        normalized_links = tuple(
            self._normalize_link(link) for link in self.links if link and link.strip()
        )

        object.__setattr__(self, "title", normalized_title)
        object.__setattr__(self, "description", normalized_description or None)
        object.__setattr__(self, "links", normalized_links)

        if not normalized_title:
            raise CandidateDomainError("project title must not be empty")

    @staticmethod
    def _normalize_link(value: str) -> str:
        normalized = value.strip()
        parsed = urlparse(normalized)

        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CandidateDomainError("project link must be a valid http/https url")

        return normalized


@dataclass(slots=True, frozen=True)
class AvatarRef:
    file_id: UUID


@dataclass(slots=True, frozen=True)
class ResumeRef:
    file_id: UUID
