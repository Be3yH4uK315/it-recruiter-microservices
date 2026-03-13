from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import candidate as models
from app.schemas import candidate as schemas


class CandidateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, candidate_id: UUID) -> models.Candidate | None:
        query = (
            select(models.Candidate)
            .where(models.Candidate.id == candidate_id)
            .options(
                selectinload(models.Candidate.skills),
                selectinload(models.Candidate.resumes),
                selectinload(models.Candidate.projects),
                selectinload(models.Candidate.experiences),
                selectinload(models.Candidate.avatars),
                selectinload(models.Candidate.education),
            )
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_telegram_id(self, telegram_id: int) -> models.Candidate | None:
        query = (
            select(models.Candidate)
            .where(models.Candidate.telegram_id == telegram_id)
            .options(
                selectinload(models.Candidate.skills),
                selectinload(models.Candidate.resumes),
                selectinload(models.Candidate.projects),
                selectinload(models.Candidate.experiences),
                selectinload(models.Candidate.avatars),
                selectinload(models.Candidate.education),
            )
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_paginated(
        self,
        limit: int,
        offset: int,
        search_query: str | None = None,
        skill_filter: str | None = None,
    ) -> tuple[int, list[models.Candidate]]:
        filters = [models.Candidate.status == models.Status.ACTIVE]

        if search_query:
            search_term = f"%{search_query}%"
            filters.append(
                or_(
                    models.Candidate.display_name.ilike(search_term),
                    models.Candidate.headline_role.ilike(search_term),
                )
            )

        if skill_filter:
            filters.append(
                models.Candidate.skills.any(models.CandidateSkill.skill.ilike(f"%{skill_filter}%"))
            )

        count_query = select(func.count()).select_from(models.Candidate).where(and_(*filters))
        total = (await self.session.execute(count_query)).scalar() or 0

        query = (
            select(models.Candidate)
            .where(and_(*filters))
            .options(
                selectinload(models.Candidate.avatars),
                selectinload(models.Candidate.skills),
            )
            .order_by(desc(models.Candidate.created_at))
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        return total, result.scalars().all()

    async def get_by_ids(self, candidate_ids: list[UUID]) -> list[models.Candidate]:
        if not candidate_ids:
            return []
        query = (
            select(models.Candidate)
            .where(models.Candidate.id.in_(candidate_ids))
            .options(
                selectinload(models.Candidate.avatars),
                selectinload(models.Candidate.skills),
            )
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create(self, candidate_in: schemas.CandidateCreate) -> models.Candidate:
        candidate_data = candidate_in.model_dump()
        skills_data = candidate_data.pop("skills", [])
        projects_data = candidate_data.pop("projects", [])
        experiences_data = candidate_data.pop("experiences", [])
        education_data = candidate_data.pop("education", [])

        db_obj = models.Candidate(**candidate_data)

        if skills_data:
            db_obj.skills = [models.CandidateSkill(**s) for s in skills_data]

        if projects_data:
            db_obj.projects = [models.Project(**p) for p in projects_data]

        if experiences_data:
            db_obj.experiences = [models.Experience(**e) for e in experiences_data]

        if education_data:
            db_obj.education = [models.Education(**e) for e in education_data]

        self.session.add(db_obj)
        return db_obj

    async def delete(self, candidate_in: models.Candidate):
        await self.session.delete(candidate_in)

    async def soft_delete(self, candidate_in: models.Candidate):
        candidate_in.status = models.Status.BLOCKED

    async def replace_avatar(self, candidate_in: models.Candidate, file_id: UUID) -> UUID | None:
        old_file_id = None

        if candidate_in.avatars:
            for old_avatar in candidate_in.avatars:
                old_file_id = old_avatar.file_id
                await self.session.delete(old_avatar)

        new_avatar = models.Avatar(candidate_id=candidate_in.id, file_id=file_id)
        self.session.add(new_avatar)

        return old_file_id

    async def delete_avatar(self, candidate_in: models.Candidate) -> UUID | None:
        if not candidate_in.avatars:
            return None

        old_avatar = candidate_in.avatars[0]
        old_file_id = old_avatar.file_id
        await self.session.delete(old_avatar)
        return old_file_id

    async def replace_resume(self, candidate_in: models.Candidate, file_id: UUID) -> UUID | None:
        old_file_id = None

        if candidate_in.resumes:
            old_resume = candidate_in.resumes[0]
            old_file_id = old_resume.file_id
            await self.session.delete(old_resume)

        new_resume = models.Resume(candidate_id=candidate_in.id, file_id=file_id)
        self.session.add(new_resume)
        return old_file_id

    async def delete_resume(self, candidate_in: models.Candidate) -> UUID | None:
        if not candidate_in.resumes:
            return None

        old_resume = candidate_in.resumes[0]
        old_file_id = old_resume.file_id
        await self.session.delete(old_resume)
        return old_file_id

    async def get_skill(self, skill_id: UUID) -> models.CandidateSkill | None:
        return await self.session.get(models.CandidateSkill, skill_id)

    def add_skill(
        self,
        candidate_id: UUID,
        skill_in: schemas.CandidateSkillCreate,
    ) -> models.CandidateSkill:
        db_skill = models.CandidateSkill(**skill_in.model_dump(), candidate_id=candidate_id)
        self.session.add(db_skill)
        return db_skill

    async def delete_skill(self, skill: models.CandidateSkill):
        await self.session.delete(skill)

    async def sync_skills(
        self,
        candidate_in: models.Candidate,
        new_skills: list[schemas.CandidateSkillCreate],
    ):
        current_map = {(s.skill, s.kind): s for s in candidate_in.skills}
        incoming_keys = set()

        for skill_in in new_skills:
            key = (skill_in.skill, skill_in.kind)
            incoming_keys.add(key)

            if key in current_map:
                if current_map[key].level != skill_in.level:
                    current_map[key].level = skill_in.level
            else:
                new_skill = models.CandidateSkill(
                    **skill_in.model_dump(),
                    candidate_id=candidate_in.id,
                )
                self.session.add(new_skill)

        for key, db_skill in current_map.items():
            if key not in incoming_keys:
                await self.session.delete(db_skill)

    async def get_project(self, project_id: UUID) -> models.Project | None:
        return await self.session.get(models.Project, project_id)

    def add_project(
        self,
        candidate_id: UUID,
        project_in: schemas.ProjectCreate,
    ) -> models.Project:
        db_project = models.Project(**project_in.model_dump(), candidate_id=candidate_id)
        self.session.add(db_project)
        return db_project

    async def delete_project(self, project: models.Project):
        await self.session.delete(project)

    async def replace_projects(
        self,
        candidate_in: models.Candidate,
        new_projects: list[schemas.ProjectCreate],
    ):
        for proj in candidate_in.projects:
            await self.session.delete(proj)

        if new_projects:
            self.session.add_all(
                [
                    models.Project(
                        **p.model_dump(),
                        candidate_id=candidate_in.id,
                    )
                    for p in new_projects
                ]
            )

    def add_experience(
        self,
        candidate_id: UUID,
        experience_in: schemas.ExperienceCreate,
    ) -> models.Experience:
        db_exp = models.Experience(**experience_in.model_dump(), candidate_id=candidate_id)
        self.session.add(db_exp)
        return db_exp

    async def replace_experiences(
        self,
        candidate_in: models.Candidate,
        new_experiences: list[schemas.ExperienceCreate],
    ) -> list[models.Experience]:
        for exp in candidate_in.experiences:
            await self.session.delete(exp)

        new_objs = []
        if new_experiences:
            new_objs = [
                models.Experience(
                    **e.model_dump(),
                    candidate_id=candidate_in.id,
                )
                for e in new_experiences
            ]
            self.session.add_all(new_objs)

        return new_objs

    async def replace_education(
        self,
        candidate_in: models.Candidate,
        new_education: list[schemas.EducationItem],
    ):
        for edu in candidate_in.education:
            await self.session.delete(edu)

        if new_education:
            self.session.add_all(
                [
                    models.Education(
                        candidate_id=candidate_in.id,
                        level=item.level,
                        institution=item.institution,
                        year=item.year,
                    )
                    for item in new_education
                ]
            )
