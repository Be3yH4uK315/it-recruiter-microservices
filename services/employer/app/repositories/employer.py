from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import employer as models
from app.schemas import employer as schemas


class EmployerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> models.Employer | None:
        query = select(models.Employer).where(models.Employer.telegram_id == telegram_id)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_id(self, employer_id: UUID) -> models.Employer | None:
        return await self.session.get(models.Employer, employer_id)

    async def create(self, employer: schemas.EmployerCreate) -> models.Employer:
        db_obj = models.Employer(**employer.model_dump())
        self.session.add(db_obj)
        return db_obj

    async def update(
        self, employer_id: UUID, update_data: schemas.EmployerUpdate
    ) -> models.Employer | None:
        """Обновление полей работодателя."""
        stmt = (
            update(models.Employer)
            .where(models.Employer.id == employer_id)
            .values(**update_data.model_dump(exclude_unset=True))
            .returning(models.Employer)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_session(self, session_id: UUID) -> models.SearchSession | None:
        return await self.session.get(models.SearchSession, session_id)

    async def create_session(
        self, employer_id: UUID, session_in: schemas.SearchSessionCreate
    ) -> models.SearchSession:
        filters_data = session_in.filters.model_dump(mode="json")

        db_obj = models.SearchSession(
            employer_id=employer_id, title=session_in.title, filters=filters_data
        )
        self.session.add(db_obj)
        return db_obj

    async def get_viewed_candidate_ids(self, session_id: UUID) -> list[UUID]:
        query = select(models.Decision.candidate_id).where(models.Decision.session_id == session_id)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create_decision(
        self, session_id: UUID, decision: schemas.DecisionCreate
    ) -> models.Decision:
        stmt = (
            insert(models.Decision)
            .values(
                session_id=session_id,
                candidate_id=decision.candidate_id,
                decision=decision.decision,
                note=decision.note,
            )
            .on_conflict_do_update(
                index_elements=["session_id", "candidate_id"],
                set_={"decision": decision.decision, "note": decision.note},
            )
            .returning(models.Decision)
        )

        result = await self.session.execute(stmt)
        return result.scalars().one()

    async def get_contact_request(
        self, employer_id: UUID, candidate_id: UUID
    ) -> models.ContactsRequest | None:
        query = select(models.ContactsRequest).where(
            and_(
                models.ContactsRequest.employer_id == employer_id,
                models.ContactsRequest.candidate_id == candidate_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def create_contact_request(
        self, employer_id: UUID, request: schemas.ContactsRequestCreate, granted: bool
    ) -> models.ContactsRequest:
        db_obj = models.ContactsRequest(
            employer_id=employer_id, candidate_id=request.candidate_id, granted=granted
        )
        self.session.add(db_obj)
        return db_obj

    async def update_contact_request_status(self, request_id: UUID, granted: bool) -> bool:
        stmt = (
            update(models.ContactsRequest)
            .where(models.ContactsRequest.id == request_id)
            .values(granted=granted)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def get_request_with_employer_tg(self, request_id: UUID):
        """Возвращает (ContactsRequest, employer_telegram_id)."""
        query = (
            select(models.ContactsRequest, models.Employer.telegram_id)
            .join(
                models.Employer,
                models.ContactsRequest.employer_id == models.Employer.id,
            )
            .where(models.ContactsRequest.id == request_id)
        )
        result = await self.session.execute(query)
        return result.first()

    async def get_favorites(self, employer_id: UUID) -> list[UUID]:
        """Возвращает список ID кандидатов, которых лайкнул этот HR (уникальные)."""
        query = (
            select(models.Decision.candidate_id)
            .join(models.SearchSession, models.Decision.session_id == models.SearchSession.id)
            .where(
                and_(
                    models.SearchSession.employer_id == employer_id,
                    models.Decision.decision == models.DecisionType.LIKE,
                )
            )
            .distinct()
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_unlocked_contacts(self, employer_id: UUID) -> list[UUID]:
        """Возвращает список ID кандидатов, контакты которых открыты этому HR."""
        query = (
            select(models.ContactsRequest.candidate_id)
            .where(
                and_(
                    models.ContactsRequest.employer_id == employer_id,
                    models.ContactsRequest.granted,
                )
            )
            .distinct()
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_sessions_by_employer(
        self, employer_id: UUID, limit: int = 10
    ) -> list[models.SearchSession]:
        """Возвращает последние поисковые сессии HR'а."""
        query = (
            select(models.SearchSession)
            .where(models.SearchSession.employer_id == employer_id)
            .order_by(models.SearchSession.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_statistics(self, employer_id: UUID) -> dict:
        """Считает воронку рекрутмента для конкретного HR."""
        viewed_q = (
            select(func.count(models.Decision.id))
            .join(models.SearchSession, models.Decision.session_id == models.SearchSession.id)
            .where(models.SearchSession.employer_id == employer_id)
        )

        liked_q = (
            select(func.count(models.Decision.id))
            .join(models.SearchSession, models.Decision.session_id == models.SearchSession.id)
            .where(
                and_(
                    models.SearchSession.employer_id == employer_id,
                    models.Decision.decision == models.DecisionType.LIKE,
                )
            )
        )

        req_q = select(func.count(models.ContactsRequest.id)).where(
            models.ContactsRequest.employer_id == employer_id
        )

        granted_q = select(func.count(models.ContactsRequest.id)).where(
            and_(models.ContactsRequest.employer_id == employer_id, models.ContactsRequest.granted)
        )

        viewed = (await self.session.execute(viewed_q)).scalar() or 0
        liked = (await self.session.execute(liked_q)).scalar() or 0
        requests = (await self.session.execute(req_q)).scalar() or 0
        granted = (await self.session.execute(granted_q)).scalar() or 0

        return {
            "total_viewed": viewed,
            "total_liked": liked,
            "total_contact_requests": requests,
            "total_contacts_granted": granted,
        }

    async def get_candidate_statistics(self, candidate_id: UUID) -> dict:
        """Считает воронку для конкретного кандидата."""
        views_q = select(func.count(models.Decision.id)).where(
            models.Decision.candidate_id == candidate_id
        )

        likes_q = select(func.count(models.Decision.id)).where(
            and_(
                models.Decision.candidate_id == candidate_id,
                models.Decision.decision == models.DecisionType.LIKE,
            )
        )

        req_q = select(func.count(models.ContactsRequest.id)).where(
            models.ContactsRequest.candidate_id == candidate_id
        )

        views = (await self.session.execute(views_q)).scalar() or 0
        likes = (await self.session.execute(likes_q)).scalar() or 0
        reqs = (await self.session.execute(req_q)).scalar() or 0

        return {"total_views": views, "total_likes": likes, "total_contact_requests": reqs}
