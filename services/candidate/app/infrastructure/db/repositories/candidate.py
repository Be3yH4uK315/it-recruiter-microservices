from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.candidate.entities import CandidateProfile
from app.domain.candidate.enums import (
    CandidateStatus,
    ContactsVisibility,
    EnglishLevel,
    SkillKind,
    WorkMode,
)
from app.domain.candidate.errors import CandidateNotFoundError
from app.domain.candidate.repository import CandidateRepository
from app.domain.candidate.value_objects import (
    AvatarRef,
    CandidateSkillVO,
    EducationItemVO,
    ExperienceItemVO,
    ProjectItemVO,
    ResumeRef,
    SalaryRange,
)
from app.infrastructure.db.models import candidate as models


class SqlAlchemyCandidateRepository(CandidateRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _full_profile_options() -> list:
        return [
            selectinload(models.Candidate.skills),
            selectinload(models.Candidate.projects),
            selectinload(models.Candidate.experiences),
            selectinload(models.Candidate.education),
        ]

    async def get_by_id(self, candidate_id: UUID) -> CandidateProfile | None:
        stmt = (
            select(models.Candidate)
            .where(models.Candidate.id == candidate_id)
            .options(*self._full_profile_options())
        )
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            return None
        return self._to_domain(orm_obj)

    async def get_by_telegram_id(self, telegram_id: int) -> CandidateProfile | None:
        stmt = (
            select(models.Candidate)
            .where(models.Candidate.telegram_id == telegram_id)
            .options(*self._full_profile_options())
        )
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            return None
        return self._to_domain(orm_obj)

    async def get_many_by_ids(self, candidate_ids: list[UUID]) -> list[CandidateProfile]:
        if not candidate_ids:
            return []

        stmt = (
            select(models.Candidate)
            .where(models.Candidate.id.in_(candidate_ids))
            .options(*self._full_profile_options())
        )
        result = await self._session.execute(stmt)
        items = result.scalars().all()

        by_id = {item.id: self._to_domain(item) for item in items}
        return [by_id[candidate_id] for candidate_id in candidate_ids if candidate_id in by_id]

    async def list_for_search(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CandidateProfile]:
        stmt = (
            select(models.Candidate)
            .where(models.Candidate.status == CandidateStatus.ACTIVE)
            .order_by(models.Candidate.created_at.asc())
            .options(*self._full_profile_options())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_domain(row) for row in rows]

    async def add(self, candidate: CandidateProfile) -> None:
        self._session.add(self._to_orm(candidate))

    async def save(self, candidate: CandidateProfile) -> None:
        stmt = select(models.Candidate).where(models.Candidate.id == candidate.id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()

        if orm_obj is None:
            raise CandidateNotFoundError(f"candidate {candidate.id} not found")

        self._apply_scalar_fields(orm_obj, candidate)

        await self._sync_skills(candidate)
        await self._sync_education(candidate)
        await self._sync_experiences(candidate)
        await self._sync_projects(candidate)

    async def delete(self, candidate: CandidateProfile) -> None:
        stmt = select(models.Candidate).where(models.Candidate.id == candidate.id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()

        if orm_obj is None:
            raise CandidateNotFoundError(f"candidate {candidate.id} not found")

        await self._session.delete(orm_obj)

    def _apply_scalar_fields(
        self,
        orm_obj: models.Candidate,
        candidate: CandidateProfile,
    ) -> None:
        orm_obj.display_name = candidate.display_name
        orm_obj.headline_role = candidate.headline_role
        orm_obj.location = candidate.location
        orm_obj.work_modes = [mode.value for mode in candidate.work_modes]
        orm_obj.contacts_visibility = candidate.contacts_visibility
        orm_obj.contacts = candidate.contacts
        orm_obj.status = candidate.status
        orm_obj.salary_min = candidate.salary_range.min_amount if candidate.salary_range else None
        orm_obj.salary_max = candidate.salary_range.max_amount if candidate.salary_range else None
        orm_obj.currency = candidate.salary_range.currency if candidate.salary_range else None
        orm_obj.english_level = candidate.english_level
        orm_obj.about_me = candidate.about_me
        orm_obj.avatar_file_id = candidate.avatar.file_id if candidate.avatar is not None else None
        orm_obj.resume_file_id = candidate.resume.file_id if candidate.resume is not None else None
        orm_obj.updated_at = candidate.updated_at

    async def _sync_skills(self, candidate: CandidateProfile) -> None:
        current_stmt = (
            select(
                models.CandidateSkill.skill,
                models.CandidateSkill.kind,
                models.CandidateSkill.level,
            )
            .where(models.CandidateSkill.candidate_id == candidate.id)
            .order_by(models.CandidateSkill.skill.asc(), models.CandidateSkill.kind.asc())
        )
        result = await self._session.execute(current_stmt)
        current = [(skill, kind.value, level) for skill, kind, level in result.all()]
        target = [
            (item.skill, item.kind.value, item.level)
            for item in sorted(candidate.skills, key=lambda x: (x.skill, x.kind.value))
        ]

        if current == target:
            return

        await self._session.execute(
            delete(models.CandidateSkill).where(models.CandidateSkill.candidate_id == candidate.id),
        )
        self._session.add_all(
            [
                models.CandidateSkill(
                    candidate_id=candidate.id,
                    skill=item.skill,
                    kind=item.kind,
                    level=item.level,
                )
                for item in candidate.skills
            ]
        )

    async def _sync_education(self, candidate: CandidateProfile) -> None:
        current_stmt = (
            select(
                models.Education.level,
                models.Education.institution,
                models.Education.year,
            )
            .where(models.Education.candidate_id == candidate.id)
            .order_by(models.Education.year.asc(), models.Education.institution.asc())
        )
        result = await self._session.execute(current_stmt)
        current = list(result.all())
        target = [
            (item.level, item.institution, item.year)
            for item in sorted(candidate.education, key=lambda x: (x.year, x.institution))
        ]

        if current == target:
            return

        await self._session.execute(
            delete(models.Education).where(models.Education.candidate_id == candidate.id),
        )
        self._session.add_all(
            [
                models.Education(
                    candidate_id=candidate.id,
                    level=item.level,
                    institution=item.institution,
                    year=item.year,
                )
                for item in candidate.education
            ]
        )

    async def _sync_experiences(self, candidate: CandidateProfile) -> None:
        current_stmt = (
            select(
                models.Experience.company,
                models.Experience.position,
                models.Experience.start_date,
                models.Experience.end_date,
                models.Experience.responsibilities,
            )
            .where(models.Experience.candidate_id == candidate.id)
            .order_by(models.Experience.start_date.asc(), models.Experience.company.asc())
        )
        result = await self._session.execute(current_stmt)
        current = list(result.all())
        target = [
            (
                item.company,
                item.position,
                item.start_date,
                item.end_date,
                item.responsibilities,
            )
            for item in sorted(
                candidate.experiences,
                key=lambda x: (x.start_date, x.company, x.position),
            )
        ]

        if current == target:
            return

        await self._session.execute(
            delete(models.Experience).where(models.Experience.candidate_id == candidate.id),
        )
        self._session.add_all(
            [
                models.Experience(
                    candidate_id=candidate.id,
                    company=item.company,
                    position=item.position,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    responsibilities=item.responsibilities,
                )
                for item in candidate.experiences
            ]
        )

    async def _sync_projects(self, candidate: CandidateProfile) -> None:
        current_stmt = (
            select(
                models.Project.title,
                models.Project.description,
                models.Project.links,
            )
            .where(models.Project.candidate_id == candidate.id)
            .order_by(models.Project.title.asc())
        )
        result = await self._session.execute(current_stmt)
        current = [
            (title, description, tuple(links or [])) for title, description, links in result.all()
        ]
        target = [
            (item.title, item.description, tuple(item.links))
            for item in sorted(candidate.projects, key=lambda x: x.title)
        ]

        if current == target:
            return

        await self._session.execute(
            delete(models.Project).where(models.Project.candidate_id == candidate.id),
        )
        self._session.add_all(
            [
                models.Project(
                    candidate_id=candidate.id,
                    title=item.title,
                    description=item.description,
                    links=list(item.links) if item.links else None,
                )
                for item in candidate.projects
            ]
        )

    def _to_domain(self, orm_obj: models.Candidate) -> CandidateProfile:
        created_at = self._ensure_utc(orm_obj.created_at)
        updated_at = self._ensure_utc(orm_obj.updated_at)

        salary_range = SalaryRange.from_scalars(
            salary_min=orm_obj.salary_min,
            salary_max=orm_obj.salary_max,
            currency=orm_obj.currency,
        )

        return CandidateProfile(
            id=orm_obj.id,
            telegram_id=orm_obj.telegram_id,
            display_name=orm_obj.display_name,
            headline_role=orm_obj.headline_role,
            location=orm_obj.location,
            work_modes=[WorkMode(mode) for mode in (orm_obj.work_modes or [])],
            contacts_visibility=ContactsVisibility(orm_obj.contacts_visibility.value),
            contacts=orm_obj.contacts,
            status=CandidateStatus(orm_obj.status.value),
            english_level=(
                EnglishLevel(orm_obj.english_level.value)
                if orm_obj.english_level is not None
                else None
            ),
            about_me=orm_obj.about_me,
            salary_range=salary_range,
            skills=[
                CandidateSkillVO(
                    skill=item.skill,
                    kind=SkillKind(item.kind.value),
                    level=item.level,
                )
                for item in orm_obj.skills
            ],
            education=[
                EducationItemVO(
                    level=item.level,
                    institution=item.institution,
                    year=item.year,
                )
                for item in orm_obj.education
            ],
            experiences=[
                ExperienceItemVO(
                    company=item.company,
                    position=item.position,
                    start_date=self._date_from_db(item.start_date),
                    end_date=self._date_from_db(item.end_date),
                    responsibilities=item.responsibilities,
                )
                for item in orm_obj.experiences
            ],
            projects=[
                ProjectItemVO(
                    title=item.title,
                    description=item.description,
                    links=tuple(item.links or []),
                )
                for item in orm_obj.projects
            ],
            avatar=AvatarRef(file_id=orm_obj.avatar_file_id) if orm_obj.avatar_file_id else None,
            resume=ResumeRef(file_id=orm_obj.resume_file_id) if orm_obj.resume_file_id else None,
            created_at=created_at,
            updated_at=updated_at,
            version_id=orm_obj.version_id,
        )

    def _to_orm(self, candidate: CandidateProfile) -> models.Candidate:
        orm_obj = models.Candidate(
            id=candidate.id,
            telegram_id=candidate.telegram_id,
            display_name=candidate.display_name,
            headline_role=candidate.headline_role,
            location=candidate.location,
            work_modes=[mode.value for mode in candidate.work_modes],
            salary_min=candidate.salary_range.min_amount if candidate.salary_range else None,
            salary_max=candidate.salary_range.max_amount if candidate.salary_range else None,
            currency=candidate.salary_range.currency if candidate.salary_range else None,
            contacts_visibility=candidate.contacts_visibility,
            contacts=candidate.contacts,
            status=candidate.status,
            english_level=candidate.english_level,
            about_me=candidate.about_me,
            avatar_file_id=candidate.avatar.file_id if candidate.avatar is not None else None,
            resume_file_id=candidate.resume.file_id if candidate.resume is not None else None,
            created_at=candidate.created_at,
            updated_at=candidate.updated_at,
            version_id=candidate.version_id,
        )

        orm_obj.skills = [
            models.CandidateSkill(
                skill=item.skill,
                kind=item.kind,
                level=item.level,
            )
            for item in candidate.skills
        ]

        orm_obj.education = [
            models.Education(
                level=item.level,
                institution=item.institution,
                year=item.year,
            )
            for item in candidate.education
        ]

        orm_obj.experiences = [
            models.Experience(
                company=item.company,
                position=item.position,
                start_date=item.start_date,
                end_date=item.end_date,
                responsibilities=item.responsibilities,
            )
            for item in candidate.experiences
        ]

        orm_obj.projects = [
            models.Project(
                title=item.title,
                description=item.description,
                links=list(item.links) if item.links else None,
            )
            for item in candidate.projects
        ]

        return orm_obj

    @staticmethod
    def _date_from_db(value: date | datetime | None) -> date | None:
        if value is None:
            return None
        return value.date() if isinstance(value, datetime) else value

    @staticmethod
    def _ensure_utc(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
