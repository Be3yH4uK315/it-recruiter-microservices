from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.employer.entities import (
    ContactRequest,
    EmployerProfile,
    SearchDecision,
    SearchSession,
)
from app.domain.employer.enums import ContactRequestStatus, DecisionType, SearchStatus, WorkMode
from app.domain.employer.errors import (
    ContactRequestNotFoundError,
    EmployerNotFoundError,
    SearchSessionNotFoundError,
)
from app.domain.employer.repository import (
    ContactRequestRepository,
    EmployerRepository,
    SearchSessionRepository,
)
from app.domain.employer.value_objects import (
    EmployerContacts,
    SalaryRange,
    SearchCandidateSnapshot,
    SearchFilters,
    SearchSessionCandidate,
    SearchSkill,
)
from app.infrastructure.db.models.employer import (
    ContactRequestModel,
    DecisionModel,
    EmployerModel,
    SearchSessionCandidateModel,
    SearchSessionModel,
)


class SqlAlchemyEmployerRepository(EmployerRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, employer_id: UUID) -> EmployerProfile | None:
        stmt = select(EmployerModel).where(EmployerModel.id == employer_id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            return None
        return self._to_domain(orm_obj)

    async def get_by_telegram_id(self, telegram_id: int) -> EmployerProfile | None:
        stmt = select(EmployerModel).where(EmployerModel.telegram_id == telegram_id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            return None
        return self._to_domain(orm_obj)

    async def add(self, employer: EmployerProfile) -> None:
        self._session.add(self._to_orm(employer))

    async def save(self, employer: EmployerProfile) -> None:
        stmt = select(EmployerModel).where(EmployerModel.id == employer.id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            raise EmployerNotFoundError(f"employer {employer.id} not found")

        orm_obj.company = employer.company
        orm_obj.contacts = employer.contacts.to_dict() if employer.contacts else None
        orm_obj.avatar_file_id = employer.avatar_file_id
        orm_obj.document_file_id = employer.document_file_id
        orm_obj.updated_at = self._normalize_datetime(employer.updated_at)

    @classmethod
    def _to_domain(cls, model: EmployerModel) -> EmployerProfile:
        return EmployerProfile(
            id=model.id,
            telegram_id=model.telegram_id,
            company=model.company,
            contacts=EmployerContacts.from_dict(model.contacts),
            avatar_file_id=model.avatar_file_id,
            document_file_id=model.document_file_id,
            created_at=cls._normalize_datetime(model.created_at),
            updated_at=cls._normalize_datetime(model.updated_at),
        )

    @classmethod
    def _to_orm(cls, entity: EmployerProfile) -> EmployerModel:
        return EmployerModel(
            id=entity.id,
            telegram_id=entity.telegram_id,
            company=entity.company,
            contacts=entity.contacts.to_dict() if entity.contacts else None,
            avatar_file_id=entity.avatar_file_id,
            document_file_id=entity.document_file_id,
            created_at=cls._normalize_datetime(entity.created_at),
            updated_at=cls._normalize_datetime(entity.updated_at),
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class SqlAlchemySearchSessionRepository(SearchSessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, session_id: UUID) -> SearchSession | None:
        stmt = select(SearchSessionModel).where(SearchSessionModel.id == session_id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            return None

        decisions = await self._get_session_decisions(session_id)
        pool_items = await self._get_session_pool(session_id)
        return self._to_domain(orm_obj, decisions, pool_items)

    async def add(self, session: SearchSession) -> None:
        self._session.add(self._to_orm(session))

    async def save(self, session: SearchSession) -> None:
        stmt = select(SearchSessionModel).where(SearchSessionModel.id == session.id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            raise SearchSessionNotFoundError(f"search session {session.id} not found")

        orm_obj.title = session.title
        orm_obj.filters = session.filters.to_primitives()
        orm_obj.search_offset = session.search_offset
        orm_obj.search_total = session.search_total
        orm_obj.status = session.status
        orm_obj.updated_at = self._normalize_datetime(session.updated_at)

    async def upsert_decision(self, session_id: UUID, decision: SearchDecision) -> None:
        stmt = select(DecisionModel).where(
            and_(
                DecisionModel.session_id == session_id,
                DecisionModel.candidate_id == decision.candidate_id,
            )
        )
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()

        if orm_obj is None:
            orm_obj = DecisionModel(
                session_id=session_id,
                candidate_id=decision.candidate_id,
                decision=decision.decision,
                note=decision.note,
                created_at=self._normalize_datetime(decision.created_at),
            )
            self._session.add(orm_obj)
            return

        orm_obj.decision = decision.decision
        orm_obj.note = decision.note
        orm_obj.created_at = self._normalize_datetime(decision.created_at)

    async def list_by_employer(
        self,
        employer_id: UUID,
        *,
        limit: int = 20,
    ) -> list[SearchSession]:
        stmt = (
            select(SearchSessionModel)
            .where(SearchSessionModel.employer_id == employer_id)
            .order_by(SearchSessionModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        items = result.scalars().all()
        session_ids = [item.id for item in items]
        decisions_by_session = await self._get_session_decisions_batch(session_ids)
        pool_by_session = await self._get_session_pool_batch(session_ids)

        sessions: list[SearchSession] = []
        for item in items:
            decisions = decisions_by_session.get(item.id, {})
            pool_items = pool_by_session.get(item.id, [])
            sessions.append(self._to_domain(item, decisions, pool_items))
        return sessions

    async def list_favorite_candidate_ids(self, employer_id: UUID) -> list[UUID]:
        stmt = (
            select(DecisionModel.candidate_id)
            .join(SearchSessionModel, SearchSessionModel.id == DecisionModel.session_id)
            .where(
                and_(
                    SearchSessionModel.employer_id == employer_id,
                    DecisionModel.decision == DecisionType.LIKE,
                )
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_viewed_candidate_ids(self, session_id: UUID) -> list[UUID]:
        stmt = select(DecisionModel.candidate_id).where(DecisionModel.session_id == session_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_pool_candidate_ids(self, session_id: UUID) -> list[UUID]:
        stmt = select(SearchSessionCandidateModel.candidate_id).where(
            SearchSessionCandidateModel.session_id == session_id
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_next_pool_candidate(self, session_id: UUID) -> SearchSessionCandidate | None:
        stmt = (
            select(SearchSessionCandidateModel)
            .where(
                and_(
                    SearchSessionCandidateModel.session_id == session_id,
                    SearchSessionCandidateModel.is_consumed.is_(False),
                )
            )
            .order_by(SearchSessionCandidateModel.rank_position.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            return None
        return self._pool_to_vo(orm_obj)

    async def replace_pool(
        self,
        session_id: UUID,
        items: list[SearchSessionCandidate],
    ) -> None:
        await self._session.execute(
            delete(SearchSessionCandidateModel).where(
                SearchSessionCandidateModel.session_id == session_id
            )
        )

        for item in items:
            self._session.add(
                SearchSessionCandidateModel(
                    id=item.id,
                    session_id=item.session_id,
                    candidate_id=item.snapshot.candidate_id,
                    rank_position=item.rank_position,
                    display_name=item.snapshot.display_name,
                    headline_role=item.snapshot.headline_role,
                    experience_years=item.snapshot.experience_years,
                    location=item.snapshot.location,
                    skills=list(item.snapshot.skills),
                    salary_min=item.snapshot.salary_min,
                    salary_max=item.snapshot.salary_max,
                    currency=item.snapshot.currency,
                    english_level=item.snapshot.english_level,
                    about_me=item.snapshot.about_me,
                    match_score=item.snapshot.match_score,
                    explanation=item.snapshot.explanation,
                    is_consumed=item.is_consumed,
                )
            )

    async def mark_pool_candidate_consumed(
        self,
        *,
        session_id: UUID,
        candidate_id: UUID,
    ) -> None:
        stmt = (
            update(SearchSessionCandidateModel)
            .where(
                and_(
                    SearchSessionCandidateModel.session_id == session_id,
                    SearchSessionCandidateModel.candidate_id == candidate_id,
                )
            )
            .values(is_consumed=True)
        )
        await self._session.execute(stmt)

    async def get_employer_statistics(self, employer_id: UUID) -> dict[str, int]:
        viewed_q = (
            select(func.count(DecisionModel.id))
            .join(SearchSessionModel, SearchSessionModel.id == DecisionModel.session_id)
            .where(SearchSessionModel.employer_id == employer_id)
        )
        liked_q = (
            select(func.count(DecisionModel.id))
            .join(SearchSessionModel, SearchSessionModel.id == DecisionModel.session_id)
            .where(
                and_(
                    SearchSessionModel.employer_id == employer_id,
                    DecisionModel.decision == DecisionType.LIKE,
                )
            )
        )
        requests_q = select(func.count(ContactRequestModel.id)).where(
            ContactRequestModel.employer_id == employer_id
        )
        granted_q = select(func.count(ContactRequestModel.id)).where(
            and_(
                ContactRequestModel.employer_id == employer_id,
                ContactRequestModel.status == ContactRequestStatus.GRANTED,
            )
        )

        viewed = int((await self._session.execute(viewed_q)).scalar() or 0)
        liked = int((await self._session.execute(liked_q)).scalar() or 0)
        requests = int((await self._session.execute(requests_q)).scalar() or 0)
        granted = int((await self._session.execute(granted_q)).scalar() or 0)

        return {
            "total_viewed": viewed,
            "total_liked": liked,
            "total_contact_requests": requests,
            "total_contacts_granted": granted,
        }

    async def get_candidate_statistics(self, candidate_id: UUID) -> dict[str, int]:
        views_q = select(func.count(DecisionModel.id)).where(
            DecisionModel.candidate_id == candidate_id
        )
        likes_q = select(func.count(DecisionModel.id)).where(
            and_(
                DecisionModel.candidate_id == candidate_id,
                DecisionModel.decision == DecisionType.LIKE,
            )
        )
        requests_q = select(func.count(ContactRequestModel.id)).where(
            ContactRequestModel.candidate_id == candidate_id
        )

        views = int((await self._session.execute(views_q)).scalar() or 0)
        likes = int((await self._session.execute(likes_q)).scalar() or 0)
        requests = int((await self._session.execute(requests_q)).scalar() or 0)

        return {
            "total_views": views,
            "total_likes": likes,
            "total_contact_requests": requests,
        }

    async def _get_session_decisions(self, session_id: UUID) -> dict[UUID, SearchDecision]:
        stmt = select(DecisionModel).where(DecisionModel.session_id == session_id)
        result = await self._session.execute(stmt)
        items = result.scalars().all()

        decisions: dict[UUID, SearchDecision] = {}
        for item in items:
            decisions[item.candidate_id] = SearchDecision(
                candidate_id=item.candidate_id,
                decision=item.decision,
                note=item.note,
                created_at=self._normalize_datetime(item.created_at),
            )
        return decisions

    async def _get_session_decisions_batch(
        self,
        session_ids: list[UUID],
    ) -> dict[UUID, dict[UUID, SearchDecision]]:
        if not session_ids:
            return {}

        stmt = select(DecisionModel).where(DecisionModel.session_id.in_(session_ids))
        result = await self._session.execute(stmt)
        items = result.scalars().all()

        decisions_by_session: dict[UUID, dict[UUID, SearchDecision]] = {
            session_id: {} for session_id in session_ids
        }
        for item in items:
            decisions_by_session.setdefault(item.session_id, {})[item.candidate_id] = (
                SearchDecision(
                    candidate_id=item.candidate_id,
                    decision=item.decision,
                    note=item.note,
                    created_at=self._normalize_datetime(item.created_at),
                )
            )
        return decisions_by_session

    async def _get_session_pool(self, session_id: UUID) -> list[SearchSessionCandidate]:
        stmt = (
            select(SearchSessionCandidateModel)
            .where(SearchSessionCandidateModel.session_id == session_id)
            .order_by(SearchSessionCandidateModel.rank_position.asc())
        )
        result = await self._session.execute(stmt)
        items = result.scalars().all()
        return [self._pool_to_vo(item) for item in items]

    async def _get_session_pool_batch(
        self,
        session_ids: list[UUID],
    ) -> dict[UUID, list[SearchSessionCandidate]]:
        if not session_ids:
            return {}

        stmt = (
            select(SearchSessionCandidateModel)
            .where(SearchSessionCandidateModel.session_id.in_(session_ids))
            .order_by(
                SearchSessionCandidateModel.session_id.asc(),
                SearchSessionCandidateModel.rank_position.asc(),
            )
        )
        result = await self._session.execute(stmt)
        items = result.scalars().all()

        pool_by_session: dict[UUID, list[SearchSessionCandidate]] = {
            session_id: [] for session_id in session_ids
        }
        for item in items:
            pool_by_session.setdefault(item.session_id, []).append(self._pool_to_vo(item))
        return pool_by_session

    @staticmethod
    def _pool_to_vo(model: SearchSessionCandidateModel) -> SearchSessionCandidate:
        return SearchSessionCandidate(
            id=model.id,
            session_id=model.session_id,
            rank_position=model.rank_position,
            snapshot=SearchCandidateSnapshot(
                candidate_id=model.candidate_id,
                display_name=model.display_name,
                headline_role=model.headline_role,
                experience_years=float(model.experience_years),
                location=model.location,
                skills=tuple(model.skills or []),
                salary_min=model.salary_min,
                salary_max=model.salary_max,
                currency=model.currency,
                english_level=model.english_level,
                about_me=model.about_me,
                match_score=float(model.match_score),
                explanation=model.explanation,
            ),
            is_consumed=model.is_consumed,
        )

    @classmethod
    def _to_domain(
        cls,
        model: SearchSessionModel,
        decisions: dict[UUID, SearchDecision],
        pool_items: list[SearchSessionCandidate],
    ) -> SearchSession:
        raw_filters = model.filters or {}

        exclude_ids_raw = raw_filters.get("exclude_ids", [])
        exclude_ids = tuple(
            UUID(item) if isinstance(item, str) else item for item in exclude_ids_raw
        )

        salary_min = raw_filters.get("salary_min")
        salary_max = raw_filters.get("salary_max")
        currency = raw_filters.get("currency")
        salary_range = None
        if salary_min is not None or salary_max is not None or currency is not None:
            salary_range = SalaryRange.from_scalars(
                salary_min=salary_min,
                salary_max=salary_max,
                currency=currency,
            )

        return SearchSession(
            id=model.id,
            employer_id=model.employer_id,
            title=model.title,
            filters=SearchFilters(
                role=raw_filters["role"],
                must_skills=tuple(
                    SearchSkill(skill=item["skill"], level=item.get("level"))
                    for item in raw_filters.get("must_skills", [])
                    if isinstance(item, dict) and "skill" in item
                ),
                nice_skills=tuple(
                    SearchSkill(skill=item["skill"], level=item.get("level"))
                    for item in raw_filters.get("nice_skills", [])
                    if isinstance(item, dict) and "skill" in item
                ),
                experience_min=raw_filters.get("experience_min"),
                experience_max=raw_filters.get("experience_max"),
                location=raw_filters.get("location"),
                work_modes=tuple(WorkMode(item) for item in raw_filters.get("work_modes", [])),
                salary_range=salary_range,
                english_level=raw_filters.get("english_level"),
                exclude_ids=exclude_ids,
                about_me=raw_filters.get("about_me"),
            ),
            status=(
                SearchStatus(model.status.value)
                if hasattr(model.status, "value")
                else SearchStatus(model.status)
            ),
            created_at=cls._normalize_datetime(model.created_at),
            updated_at=cls._normalize_datetime(model.updated_at),
            decisions=decisions,
            candidate_pool=pool_items,
            search_offset=model.search_offset,
            search_total=model.search_total,
        )

    @classmethod
    def _to_orm(cls, entity: SearchSession) -> SearchSessionModel:
        return SearchSessionModel(
            id=entity.id,
            employer_id=entity.employer_id,
            title=entity.title,
            filters=entity.filters.to_primitives(),
            search_offset=entity.search_offset,
            search_total=entity.search_total,
            status=entity.status,
            created_at=cls._normalize_datetime(entity.created_at),
            updated_at=cls._normalize_datetime(entity.updated_at),
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class SqlAlchemyContactRequestRepository(ContactRequestRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, request_id: UUID) -> ContactRequest | None:
        stmt = select(ContactRequestModel).where(ContactRequestModel.id == request_id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            return None
        return self._to_domain(orm_obj)

    async def get_by_employer_and_candidate(
        self,
        *,
        employer_id: UUID,
        candidate_id: UUID,
    ) -> ContactRequest | None:
        stmt = select(ContactRequestModel).where(
            and_(
                ContactRequestModel.employer_id == employer_id,
                ContactRequestModel.candidate_id == candidate_id,
            )
        )
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            return None
        return self._to_domain(orm_obj)

    async def add(self, request: ContactRequest) -> None:
        self._session.add(self._to_orm(request))

    async def save(self, request: ContactRequest) -> None:
        stmt = select(ContactRequestModel).where(ContactRequestModel.id == request.id)
        result = await self._session.execute(stmt)
        orm_obj = result.scalar_one_or_none()
        if orm_obj is None:
            raise ContactRequestNotFoundError(f"contact request {request.id} not found")

        orm_obj.status = request.status
        orm_obj.responded_at = self._normalize_datetime_or_none(request.responded_at)

    async def list_by_candidate(
        self,
        *,
        candidate_id: UUID,
        limit: int = 20,
    ) -> list[ContactRequest]:
        stmt = (
            select(ContactRequestModel)
            .where(ContactRequestModel.candidate_id == candidate_id)
            .order_by(ContactRequestModel.created_at.desc())
            .limit(max(1, min(limit, 50)))
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(item) for item in result.scalars().all()]

    async def list_unlocked_candidate_ids(self, employer_id: UUID) -> list[UUID]:
        stmt = select(ContactRequestModel.candidate_id).where(
            and_(
                ContactRequestModel.employer_id == employer_id,
                ContactRequestModel.status == ContactRequestStatus.GRANTED,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    def _to_domain(cls, model: ContactRequestModel) -> ContactRequest:
        return ContactRequest(
            id=model.id,
            employer_id=model.employer_id,
            candidate_id=model.candidate_id,
            status=(
                ContactRequestStatus(model.status.value)
                if hasattr(model.status, "value")
                else ContactRequestStatus(model.status)
            ),
            created_at=cls._normalize_datetime(model.created_at),
            responded_at=cls._normalize_datetime_or_none(model.responded_at),
        )

    @classmethod
    def _to_orm(cls, entity: ContactRequest) -> ContactRequestModel:
        return ContactRequestModel(
            id=entity.id,
            employer_id=entity.employer_id,
            candidate_id=entity.candidate_id,
            status=entity.status,
            responded_at=cls._normalize_datetime_or_none(entity.responded_at),
            created_at=cls._normalize_datetime(entity.created_at),
        )

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _normalize_datetime_or_none(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
