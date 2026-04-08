from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone

from app.application.candidates.dto.views import (
    CandidateEducationView,
    CandidateExperienceView,
    CandidateProfileView,
    CandidateProjectView,
    CandidateSkillView,
)
from app.application.common.contracts import FileGateway
from app.application.common.uow import UnitOfWork
from app.domain.candidate.entities import ExperienceItemVO
from app.domain.candidate.errors import CandidateNotFoundError, IntegrationUnavailableError


class GetCandidateProfileByTelegramHandler:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        file_gateway: FileGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._file_gateway = file_gateway

    async def __call__(self, telegram_id: int) -> CandidateProfileView:
        async with self._uow_factory() as uow:
            candidate = await uow.candidates.get_by_telegram_id(telegram_id)
            if candidate is None:
                raise CandidateNotFoundError(f"candidate telegram_id={telegram_id} not found")

        salary_range = candidate.salary_range

        avatar_file_id = candidate.avatar.file_id if candidate.avatar is not None else None
        resume_file_id = candidate.resume.file_id if candidate.resume is not None else None

        avatar_download_url = None
        if avatar_file_id is not None:
            try:
                avatar_download_url_result = await self._file_gateway.get_file_download_url(
                    file_id=avatar_file_id,
                    owner_id=candidate.id,
                )
                avatar_download_url = avatar_download_url_result.download_url
            except IntegrationUnavailableError:
                avatar_download_url = None

        resume_download_url = None
        if resume_file_id is not None:
            try:
                resume_download_url_result = await self._file_gateway.get_file_download_url(
                    file_id=resume_file_id,
                    owner_id=candidate.id,
                )
                resume_download_url = resume_download_url_result.download_url
            except IntegrationUnavailableError:
                resume_download_url = None

        return CandidateProfileView(
            id=candidate.id,
            telegram_id=candidate.telegram_id,
            display_name=candidate.display_name,
            headline_role=candidate.headline_role,
            location=candidate.location,
            work_modes=list(candidate.work_modes),
            experience_years=self._calculate_experience_years(candidate.experiences),
            contacts_visibility=candidate.contacts_visibility,
            contacts=candidate.contacts,
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
