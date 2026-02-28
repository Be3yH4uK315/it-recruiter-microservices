from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import and_, desc, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import candidate
from app.schemas import candidate as schemas

class CandidateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, candidate_id: UUID) -> Optional[candidate.Candidate]:
        query = select(candidate.Candidate).where(candidate.Candidate.id == candidate_id).options(
            selectinload(candidate.Candidate.skills),
            selectinload(candidate.Candidate.resumes),
            selectinload(candidate.Candidate.projects),
            selectinload(candidate.Candidate.experiences),
            selectinload(candidate.Candidate.avatars),
            selectinload(candidate.Candidate.education)
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[candidate.Candidate]:
        query = select(candidate.Candidate).where(candidate.Candidate.telegram_id == telegram_id).options(
            selectinload(candidate.Candidate.skills),
            selectinload(candidate.Candidate.resumes),
            selectinload(candidate.Candidate.projects),
            selectinload(candidate.Candidate.experiences),
            selectinload(candidate.Candidate.avatars),
            selectinload(candidate.Candidate.education)
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_paginated(
        self,
        limit: int,
        offset: int,
        search_query: Optional[str] = None,
        skill_filter: Optional[str] = None,
    ) -> Tuple[int, List[candidate.Candidate]]:
        filters = [candidate.Candidate.status == candidate.Status.ACTIVE]

        if search_query:
            search_term = f"%{search_query}%"
            filters.append(
                or_(
                    candidate.Candidate.display_name.ilike(search_term),
                    candidate.Candidate.headline_role.ilike(search_term),
                )
            )

        if skill_filter:
            filters.append(
                candidate.Candidate.skills.any(
                    candidate.CandidateSkill.name.ilike(f"%{skill_filter}%")
                )
            )

        count_query = (
            select(func.count())
            .select_from(candidate.Candidate)
            .where(and_(*filters))
        )
        total = (await self.session.execute(count_query)).scalar() or 0

        query = (
            select(candidate.Candidate)
            .where(and_(*filters))
            .options(
                selectinload(candidate.Candidate.avatars),
                selectinload(candidate.Candidate.skills),
            )
            .order_by(desc(candidate.Candidate.created_at))
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        return total, result.scalars().all()

    async def get_by_ids(self, candidate_ids: List[UUID]) -> List[candidate.Candidate]:
        if not candidate_ids:
            return []
        query = select(candidate.Candidate).where(candidate.Candidate.id.in_(candidate_ids)).options(
             selectinload(candidate.Candidate.avatars),
             selectinload(candidate.Candidate.skills)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create(self, candidate_in: schemas.CandidateCreate) -> candidate.Candidate:
        candidate_data = candidate_in.model_dump()
        skills_data = candidate_data.pop("skills", [])
        projects_data = candidate_data.pop("projects", [])
        experiences_data = candidate_data.pop("experiences", [])
        education_data = candidate_data.pop("education", [])

        db_obj = candidate.Candidate(**candidate_data)

        if skills_data:
            db_obj.skills = [candidate.CandidateSkill(**s) for s in skills_data]
        
        if projects_data:
            db_obj.projects = [candidate.Project(**p) for p in projects_data]
            
        if experiences_data:
            db_obj.experiences = [candidate.Experience(**e) for e in experiences_data]
            
        if education_data:
            db_obj.education = [candidate.Education(**e) for e in education_data]

        self.session.add(db_obj)
        return db_obj

    async def delete(self, candidate: candidate.Candidate):
        await self.session.delete(candidate)
    
    async def soft_delete(self, candidate: candidate.Candidate):
        candidate.status = candidate.Status.BLOCKED

    async def replace_avatar(
        self, candidate: candidate.Candidate, file_id: UUID
    ) -> Optional[UUID]:
        old_file_id = None

        if candidate.avatars:
            for old_avatar in candidate.avatars:
                old_file_id = old_avatar.file_id
                await self.session.delete(old_avatar)

        new_avatar = candidate.Avatar(candidate_id=candidate.id, file_id=file_id)
        self.session.add(new_avatar)
        
        return old_file_id

    async def delete_avatar(
        self, candidate: candidate.Candidate
    ) -> Optional[UUID]:
        if not candidate.avatars:
            return None

        old_avatar = candidate.avatars[0]
        old_file_id = old_avatar.file_id
        await self.session.delete(old_avatar)
        return old_file_id

    async def replace_resume(
        self, candidate: candidate.Candidate, file_id: UUID
    ) -> Optional[UUID]:
        old_file_id = None

        if candidate.resumes:
            old_resume = candidate.resumes[0]
            old_file_id = old_resume.file_id
            await self.session.delete(old_resume)

        new_resume = candidate.Resume(candidate_id=candidate.id, file_id=file_id)
        self.session.add(new_resume)
        return old_file_id

    async def delete_resume(
        self, candidate: candidate.Candidate
    ) -> Optional[UUID]:
        if not candidate.resumes:
            return None

        old_resume = candidate.resumes[0]
        old_file_id = old_resume.file_id
        await self.session.delete(old_resume)
        return old_file_id

    async def get_skill(
        self, skill_id: UUID
    ) -> Optional[candidate.CandidateSkill]:
        return await self.session.get(candidate.CandidateSkill, skill_id)

    def add_skill(
        self,
        candidate_id: UUID,
        skill_in: schemas.CandidateSkillCreate,
    ) -> candidate.CandidateSkill:
        db_skill = candidate.CandidateSkill(
            **skill_in.model_dump(), candidate_id=candidate_id
        )
        self.session.add(db_skill)
        return db_skill

    async def delete_skill(self, skill: candidate.CandidateSkill):
        await self.session.delete(skill)

    async def sync_skills(
        self,
        candidate: candidate.Candidate,
        new_skills: List[schemas.CandidateSkillCreate],
    ):
        current_map = {(s.skill, s.kind): s for s in candidate.skills}
        incoming_keys = set()

        for skill_in in new_skills:
            key = (skill_in.skill, skill_in.kind)
            incoming_keys.add(key)

            if key in current_map:
                if current_map[key].level != skill_in.level:
                    current_map[key].level = skill_in.level
            else:
                new_skill = candidate.CandidateSkill(
                    **skill_in.model_dump(),
                    candidate_id=candidate.id,
                )
                self.session.add(new_skill)

        for key, db_skill in current_map.items():
            if key not in incoming_keys:
                await self.session.delete(db_skill)

    async def get_project(
        self, project_id: UUID
    ) -> Optional[candidate.Project]:
        return await self.session.get(candidate.Project, project_id)

    def add_project(
        self,
        candidate_id: UUID,
        project_in: schemas.ProjectCreate,
    ) -> candidate.Project:
        db_project = candidate.Project(
            **project_in.model_dump(), candidate_id=candidate_id
        )
        self.session.add(db_project)
        return db_project

    async def delete_project(self, project: candidate.Project):
        await self.session.delete(project)

    async def replace_projects(
        self,
        candidate: candidate.Candidate,
        new_projects: List[schemas.ProjectCreate],
    ):
        for proj in candidate.projects:
            await self.session.delete(proj)

        if new_projects:
            self.session.add_all(
                [
                    candidate.Project(
                        **p.model_dump(),
                        candidate_id=candidate.id,
                    )
                    for p in new_projects
                ]
            )

    def add_experience(
        self,
        candidate_id: UUID,
        experience_in: schemas.ExperienceCreate,
    ) -> candidate.Experience:
        db_exp = candidate.Experience(
            **experience_in.model_dump(), candidate_id=candidate_id
        )
        self.session.add(db_exp)
        return db_exp

    async def replace_experiences(
        self,
        candidate: candidate.Candidate,
        new_experiences: List[schemas.ExperienceCreate],
    ) -> List[candidate.Experience]:
        for exp in candidate.experiences:
            await self.session.delete(exp)

        new_objs = []
        if new_experiences:
            new_objs = [
                candidate.Experience(
                    **e.model_dump(),
                    candidate_id=candidate.id,
                )
                for e in new_experiences
            ]
            self.session.add_all(new_objs)

        return new_objs

    async def replace_education(
        self,
        candidate: candidate.Candidate,
        new_education: List[schemas.EducationItem],
    ):
        for edu in candidate.education:
            await self.session.delete(edu)

        if new_education:
            self.session.add_all(
                [
                    candidate.Education(
                        candidate_id=candidate.id,
                        level=item.level,
                        institution=item.institution,
                        year=item.year,
                    )
                    for item in new_education
                ]
            )