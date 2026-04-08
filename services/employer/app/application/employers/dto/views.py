from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.domain.employer.entities import EmployerProfile, SearchSession
from app.domain.employer.value_objects import SearchFilters


class ContactRequestStatusView(StrEnum):
    PENDING = "pending"
    GRANTED = "granted"
    REJECTED = "rejected"
    NOT_FOUND = "not_found"


def map_contact_request_status_to_view(status) -> ContactRequestStatusView:
    value = getattr(status, "value", str(status)).strip().lower()

    if value == "pending":
        return ContactRequestStatusView.PENDING
    if value == "granted":
        return ContactRequestStatusView.GRANTED
    if value == "rejected":
        return ContactRequestStatusView.REJECTED

    return ContactRequestStatusView.NOT_FOUND


@dataclass(slots=True, frozen=True)
class EmployerView:
    id: UUID
    telegram_id: int
    company: str | None
    contacts: dict[str, str | None] | None
    avatar_file_id: UUID | None
    avatar_download_url: str | None
    document_file_id: UUID | None
    document_download_url: str | None
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, employer: EmployerProfile) -> "EmployerView":
        return cls(
            id=employer.id,
            telegram_id=employer.telegram_id,
            company=employer.company,
            contacts=employer.contacts.to_dict() if employer.contacts else None,
            avatar_file_id=employer.avatar_file_id,
            avatar_download_url=None,
            document_file_id=employer.document_file_id,
            document_download_url=None,
            created_at=employer.created_at,
            updated_at=employer.updated_at,
        )


@dataclass(slots=True, frozen=True)
class SearchSessionView:
    id: UUID
    employer_id: UUID
    title: str
    filters: dict
    status: str
    created_at: datetime | None
    updated_at: datetime | None
    search_offset: int
    search_total: int
    candidate_pool_size: int

    @classmethod
    def from_entity(cls, session: SearchSession) -> "SearchSessionView":
        return cls(
            id=session.id,
            employer_id=session.employer_id,
            title=session.title,
            filters=_filters_to_dict(session.filters),
            status=session.status.value,
            created_at=session.created_at,
            updated_at=session.updated_at,
            search_offset=session.search_offset,
            search_total=session.search_total,
            candidate_pool_size=len(session.candidate_pool),
        )


@dataclass(slots=True, frozen=True)
class EmployerStatisticsView:
    total_viewed: int
    total_liked: int
    total_contact_requests: int
    total_contacts_granted: int


@dataclass(slots=True, frozen=True)
class CandidateStatisticsView:
    total_views: int
    total_likes: int
    total_contact_requests: int


def _filters_to_dict(filters: SearchFilters) -> dict:
    return {
        "role": filters.role,
        "must_skills": [{"skill": item.skill, "level": item.level} for item in filters.must_skills],
        "nice_skills": [{"skill": item.skill, "level": item.level} for item in filters.nice_skills],
        "experience_min": filters.experience_min,
        "experience_max": filters.experience_max,
        "location": filters.location,
        "work_modes": [item.value for item in filters.work_modes],
        "exclude_ids": [str(item) for item in filters.exclude_ids],
        "salary_min": filters.salary_range.min_amount if filters.salary_range else None,
        "salary_max": filters.salary_range.max_amount if filters.salary_range else None,
        "currency": filters.salary_range.currency if filters.salary_range else None,
        "english_level": filters.english_level,
        "about_me": filters.about_me,
    }
