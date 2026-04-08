from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.application.common.contracts import EventMapper
from app.domain.candidate.entities import (
    CandidateAvatarDeleted,
    CandidateAvatarReplaced,
    CandidateCreated,
    CandidateProfile,
    CandidateProfileUpdated,
    CandidateResumeDeleted,
    CandidateResumeReplaced,
)
from app.domain.candidate.enums import CandidateStatus
from app.domain.common.events import DomainEvent


class DefaultEventMapper(EventMapper):
    def map_domain_event(
        self,
        *,
        event: DomainEvent,
        candidate: CandidateProfile,
    ) -> list[tuple[str, dict]]:
        messages: list[tuple[str, dict]] = []

        base_payload = {
            "event_id": self._serialize_uuid(event.event_id),
            "occurred_at": self._serialize_dt(event.occurred_at),
            "event_name": event.event_name,
            "candidate_id": self._serialize_uuid(candidate.id),
        }

        if isinstance(event, CandidateCreated):
            messages.append(
                (
                    "candidate.created",
                    {
                        **base_payload,
                        "telegram_id": candidate.telegram_id,
                        "snapshot": self._build_candidate_snapshot(candidate),
                    },
                )
            )
            messages.append(self._build_search_sync_message(base_payload, candidate))
            return messages

        if isinstance(event, CandidateProfileUpdated):
            messages.append(
                (
                    "candidate.updated",
                    {
                        **base_payload,
                        "snapshot": self._build_candidate_snapshot(candidate),
                    },
                )
            )
            messages.append(self._build_search_sync_message(base_payload, candidate))
            return messages

        if isinstance(event, CandidateAvatarReplaced):
            messages.append(
                (
                    "candidate.avatar.replaced",
                    {
                        **base_payload,
                        "new_file_id": self._serialize_uuid(event.new_file_id),
                        "old_file_id": self._serialize_uuid(event.old_file_id),
                    },
                )
            )
            messages.append(self._build_search_sync_message(base_payload, candidate))
            return messages

        if isinstance(event, CandidateAvatarDeleted):
            messages.append(
                (
                    "candidate.avatar.deleted",
                    {
                        **base_payload,
                        "file_id": self._serialize_uuid(event.file_id),
                    },
                )
            )
            messages.append(self._build_search_sync_message(base_payload, candidate))
            return messages

        if isinstance(event, CandidateResumeReplaced):
            messages.append(
                (
                    "candidate.resume.replaced",
                    {
                        **base_payload,
                        "new_file_id": self._serialize_uuid(event.new_file_id),
                        "old_file_id": self._serialize_uuid(event.old_file_id),
                    },
                )
            )
            messages.append(self._build_search_sync_message(base_payload, candidate))
            return messages

        if isinstance(event, CandidateResumeDeleted):
            messages.append(
                (
                    "candidate.resume.deleted",
                    {
                        **base_payload,
                        "file_id": self._serialize_uuid(event.file_id),
                    },
                )
            )
            messages.append(self._build_search_sync_message(base_payload, candidate))
            return messages

        return messages

    def _build_search_sync_message(
        self,
        base_payload: dict,
        candidate: CandidateProfile,
    ) -> tuple[str, dict]:
        if candidate.status == CandidateStatus.ACTIVE:
            return (
                "search.candidate.sync.requested",
                {
                    **base_payload,
                    "operation": "upsert",
                    "snapshot": self._build_candidate_snapshot(candidate),
                },
            )

        return (
            "search.candidate.sync.requested",
            {
                **base_payload,
                "operation": "delete",
            },
        )

    def _build_candidate_snapshot(self, candidate: CandidateProfile) -> dict:
        return {
            "id": self._serialize_uuid(candidate.id),
            "telegram_id": candidate.telegram_id,
            "display_name": candidate.display_name,
            "headline_role": candidate.headline_role,
            "location": candidate.location,
            "work_modes": [item.value for item in candidate.work_modes],
            "contacts_visibility": candidate.contacts_visibility.value,
            "status": candidate.status.value,
            "english_level": candidate.english_level.value if candidate.english_level else None,
            "about_me": candidate.about_me,
            "salary_min": candidate.salary_range.min_amount if candidate.salary_range else None,
            "salary_max": candidate.salary_range.max_amount if candidate.salary_range else None,
            "currency": candidate.salary_range.currency if candidate.salary_range else None,
            "skills": [
                {
                    "skill": item.skill,
                    "kind": item.kind.value,
                    "level": item.level,
                }
                for item in candidate.skills
            ],
            "education": [
                {
                    "level": item.level,
                    "institution": item.institution,
                    "year": item.year,
                }
                for item in candidate.education
            ],
            "experiences": [
                {
                    "company": item.company,
                    "position": item.position,
                    "start_date": item.start_date.isoformat(),
                    "end_date": item.end_date.isoformat() if item.end_date else None,
                    "responsibilities": item.responsibilities,
                }
                for item in candidate.experiences
            ],
            "projects": [
                {
                    "title": item.title,
                    "description": item.description,
                    "links": list(item.links),
                }
                for item in candidate.projects
            ],
            "avatar_file_id": (
                self._serialize_uuid(candidate.avatar.file_id)
                if candidate.avatar is not None
                else None
            ),
            "resume_file_id": (
                self._serialize_uuid(candidate.resume.file_id)
                if candidate.resume is not None
                else None
            ),
            "created_at": (
                self._serialize_dt(candidate.created_at) if candidate.created_at else None
            ),
            "updated_at": (
                self._serialize_dt(candidate.updated_at) if candidate.updated_at else None
            ),
            "version_id": candidate.version_id,
        }

    @staticmethod
    def _serialize_uuid(value: UUID | None) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _serialize_dt(value: datetime) -> str:
        return value.isoformat()
