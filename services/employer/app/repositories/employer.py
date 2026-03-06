from uuid import UUID

from sqlalchemy import and_, select, update
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
