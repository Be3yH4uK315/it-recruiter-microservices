from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from app.application.candidates.dto.views import (
    CandidateEducationView,
    CandidateEmployerView,
    CandidateExperienceView,
    CandidateProjectView,
    CandidateSkillView,
)
from app.application.candidates.services.contact_access_policy import ContactAccessPolicy
from app.application.common.contracts import EmployerGateway, FileGateway
from app.application.common.uow import UnitOfWork
from app.domain.candidate.enums import CandidateStatus
from app.domain.candidate.errors import CandidateNotFoundError, IntegrationUnavailableError
from app.domain.candidate.value_objects import ExperienceItemVO


@dataclass(slots=True, frozen=True)
class GetCandidateForEmployerQuery:
    candidate_id: UUID
    employer_telegram_id: int


class GetCandidateForEmployerHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        employer_gateway: EmployerGateway,
        access_policy: ContactAccessPolicy,
        file_gateway: FileGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._employer_gateway = employer_gateway
        self._access_policy = access_policy
        self._file_gateway = file_gateway

    async def __call__(
        self,
        query: GetCandidateForEmployerQuery,
    ) -> CandidateEmployerView:
        async with self._uow_factory() as uow:
            candidate = await uow.candidates.get_by_id(query.candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(
                    f"candidate {query.candidate_id} not found",
                )

        if candidate.status != CandidateStatus.ACTIVE:
            raise CandidateNotFoundError(f"candidate {query.candidate_id} not found")

        avatar_file_id = candidate.avatar.file_id if candidate.avatar is not None else None
        resume_file_id = candidate.resume.file_id if candidate.resume is not None else None

        employer_has_access, avatar_download_url, resume_download_url = await asyncio.gather(
            self._employer_gateway.has_contact_access(
                candidate_id=query.candidate_id,
                employer_telegram_id=query.employer_telegram_id,
            ),
            self._safe_download_url(file_id=avatar_file_id, owner_id=candidate.id),
            self._safe_download_url(file_id=resume_file_id, owner_id=candidate.id),
        )

        access_decision = self._access_policy.evaluate(
            candidate=candidate,
            employer_has_access=employer_has_access,
        )

        salary_range = candidate.salary_range
        experience_years = self._calculate_experience_years(candidate.experiences)

        return CandidateEmployerView(
            id=candidate.id,
            display_name=candidate.display_name,
            headline_role=candidate.headline_role,
            location=candidate.location,
            work_modes=list(candidate.work_modes),
            experience_years=experience_years,
            contacts_visibility=candidate.contacts_visibility,
            contacts=candidate.contacts if access_decision.can_view_contacts else None,
            can_view_contacts=access_decision.can_view_contacts,
            status=candidate.status,
            english_level=candidate.english_level,
            about_me=candidate.about_me,
            salary_min=salary_range.min_amount if salary_range is not None else None,
            salary_max=salary_range.max_amount if salary_range is not None else None,
            currency=salary_range.currency if salary_range is not None else None,
            skills=[
                CandidateSkillView(
                    skill=item.skill,
                    kind=item.kind,
                    level=item.level,
                )
                for item in candidate.skills
            ],
            education=[
                CandidateEducationView(
                    level=item.level,
                    institution=item.institution,
                    year=item.year,
                )
                for item in candidate.education
            ],
            experiences=[
                CandidateExperienceView(
                    company=item.company,
                    position=item.position,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    responsibilities=item.responsibilities,
                )
                for item in candidate.experiences
            ],
            projects=[
                CandidateProjectView(
                    title=item.title,
                    description=item.description,
                    links=list(item.links),
                )
                for item in candidate.projects
            ],
            avatar_file_id=avatar_file_id,
            avatar_download_url=avatar_download_url,
            resume_file_id=resume_file_id,
            resume_download_url=resume_download_url,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
            version_id=candidate.version_id,
        )

    @staticmethod
    def _calculate_experience_years(experiences: list[ExperienceItemVO]) -> float:
        intervals: list[tuple[date, date]] = []
        today = datetime.now(timezone.utc).date()

        for item in experiences:
            start_date = item.start_date
            end_date = item.end_date or today

            if end_date < start_date:
                continue

            intervals.append((start_date, end_date))

        if not intervals:
            return 0.0

        intervals.sort(key=lambda item: item[0])

        merged: list[tuple[date, date]] = []
        current_start, current_end = intervals[0]

        for start_date, end_date in intervals[1:]:
            if start_date <= current_end:
                if end_date > current_end:
                    current_end = end_date
                continue

            merged.append((current_start, current_end))
            current_start, current_end = start_date, end_date

        merged.append((current_start, current_end))

        total_days = sum((end_date - start_date).days for start_date, end_date in merged)
        return round(total_days / 365.25, 2)

    async def _safe_download_url(
        self,
        *,
        file_id: UUID | None,
        owner_id: UUID,
    ) -> str | None:
        if file_id is None:
            return None

        try:
            result = await self._file_gateway.get_file_download_url(
                file_id=file_id,
                owner_id=owner_id,
            )
        except IntegrationUnavailableError:
            return None

        return result.download_url
