from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.employer.entities import ContactRequest, SearchDecision, SearchSession
from app.domain.employer.enums import ContactRequestStatus, DecisionType, WorkMode
from app.domain.employer.errors import EmployerNotFoundError, SearchSessionNotFoundError
from app.domain.employer.value_objects import (
    EmployerContacts,
    SalaryRange,
    SearchCandidateSnapshot,
    SearchFilters,
    SearchSessionCandidate,
    SearchSkill,
)
from app.infrastructure.db.repositories.employer import (
    SqlAlchemyContactRequestRepository,
    SqlAlchemyEmployerRepository,
    SqlAlchemySearchSessionRepository,
)


def build_employer(*, telegram_id: int = 1001, company: str = "Acme"):
    from app.domain.employer.entities import EmployerProfile

    return EmployerProfile.create(
        id=uuid4(),
        telegram_id=telegram_id,
        company=company,
        contacts=EmployerContacts(
            email="hr@acme.test",
            telegram="@acme_hr",
        ),
    )


def build_search_session(*, employer_id: UUID, title: str = "Python Search") -> SearchSession:
    session = SearchSession.create(
        id=uuid4(),
        employer_id=employer_id,
        title=title,
        filters=SearchFilters(
            role="Python Developer",
            must_skills=(
                SearchSkill(skill="python", level=5),
                SearchSkill(skill="fastapi", level=4),
            ),
            nice_skills=(),
            experience_min=3,
            experience_max=6,
            location="Paris",
            work_modes=(WorkMode.REMOTE, WorkMode.HYBRID),
            salary_range=SalaryRange.from_scalars(
                salary_min=200000,
                salary_max=350000,
                currency="RUB",
            ),
            english_level="B2",
            exclude_ids=(),
        ),
    )
    session.candidate_pool = [
        SearchSessionCandidate(
            id=uuid4(),
            session_id=session.id,
            rank_position=0,
            snapshot=SearchCandidateSnapshot(
                candidate_id=UUID("00000000-0000-0000-0000-000000000001"),
                display_name="Alice",
                headline_role="Python Developer",
                experience_years=4.5,
                location="Paris",
                skills=({"skill": "python", "level": 5},),
                salary_min=250000,
                salary_max=350000,
                currency="RUB",
                english_level="B2",
                about_me="Backend engineer",
                match_score=0.92,
                explanation={"rrf": 0.91},
            ),
            is_consumed=False,
        )
    ]
    session.search_offset = 50
    session.search_total = 100
    return session


@pytest.mark.asyncio
async def test_employer_repository_add_and_get_by_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    employer = build_employer()

    async with session_factory() as session:
        repo = SqlAlchemyEmployerRepository(session)
        await repo.add(employer)
        await session.commit()

    async with session_factory() as session:
        repo = SqlAlchemyEmployerRepository(session)
        loaded = await repo.get_by_id(employer.id)

    assert loaded is not None
    assert loaded.id == employer.id
    assert loaded.telegram_id == employer.telegram_id
    assert loaded.company == "Acme"
    assert loaded.contacts is not None
    assert loaded.contacts.email == "hr@acme.test"


@pytest.mark.asyncio
async def test_employer_repository_get_by_telegram_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    employer = build_employer(telegram_id=2002, company="Globex")

    async with session_factory() as session:
        repo = SqlAlchemyEmployerRepository(session)
        await repo.add(employer)
        await session.commit()

    async with session_factory() as session:
        repo = SqlAlchemyEmployerRepository(session)
        loaded = await repo.get_by_telegram_id(2002)

    assert loaded is not None
    assert loaded.company == "Globex"


@pytest.mark.asyncio
async def test_employer_repository_save_updates_fields(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    employer = build_employer()

    async with session_factory() as session:
        repo = SqlAlchemyEmployerRepository(session)
        await repo.add(employer)
        await session.commit()

    employer.update_profile(
        company="Acme Updated",
        contacts=EmployerContacts(
            email="new@acme.test",
            telegram="@new_acme",
        ),
    )

    async with session_factory() as session:
        repo = SqlAlchemyEmployerRepository(session)
        await repo.save(employer)
        await session.commit()

    async with session_factory() as session:
        repo = SqlAlchemyEmployerRepository(session)
        loaded = await repo.get_by_id(employer.id)

    assert loaded is not None
    assert loaded.company == "Acme Updated"
    assert loaded.contacts is not None
    assert loaded.contacts.email == "new@acme.test"


@pytest.mark.asyncio
async def test_employer_repository_save_raises_when_missing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    employer = build_employer()

    async with session_factory() as session:
        repo = SqlAlchemyEmployerRepository(session)
        with pytest.raises(EmployerNotFoundError):
            await repo.save(employer)


@pytest.mark.asyncio
async def test_search_session_repository_add_and_get_by_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    employer = build_employer()
    session_entity = build_search_session(employer_id=employer.id)

    async with session_factory() as session:
        employer_repo = SqlAlchemyEmployerRepository(session)
        search_repo = SqlAlchemySearchSessionRepository(session)
        await employer_repo.add(employer)
        await search_repo.add(session_entity)
        await session.commit()

    async with session_factory() as session:
        search_repo = SqlAlchemySearchSessionRepository(session)
        loaded = await search_repo.get_by_id(session_entity.id)

    assert loaded is not None
    assert loaded.id == session_entity.id
    assert loaded.title == "Python Search"
    assert loaded.filters.role == "Python Developer"
    assert loaded.search_offset == 50
    assert loaded.search_total == 100
    assert len(loaded.candidate_pool) == 0


@pytest.mark.asyncio
async def test_search_session_repository_save_updates_entity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    employer = build_employer()
    session_entity = build_search_session(employer_id=employer.id)

    async with session_factory() as session:
        employer_repo = SqlAlchemyEmployerRepository(session)
        search_repo = SqlAlchemySearchSessionRepository(session)
        await employer_repo.add(employer)
        await search_repo.add(session_entity)
        await session.commit()

    session_entity.title = "Updated Search"
    session_entity.candidate_pool = [
        SearchSessionCandidate(
            id=uuid4(),
            session_id=session_entity.id,
            rank_position=0,
            snapshot=SearchCandidateSnapshot(
                candidate_id=UUID("00000000-0000-0000-0000-000000000002"),
                display_name="Bob",
                headline_role="Backend Engineer",
                experience_years=5.0,
                location="Berlin",
                skills=({"skill": "fastapi", "level": 4},),
                salary_min=270000,
                salary_max=370000,
                currency="RUB",
                english_level="B2",
                about_me="Distributed systems",
                match_score=0.88,
                explanation={"rrf": 0.84},
            ),
            is_consumed=False,
        )
    ]
    session_entity.search_offset = 100
    session_entity.search_total = 120

    async with session_factory() as session:
        search_repo = SqlAlchemySearchSessionRepository(session)
        await search_repo.save(session_entity)
        await session.commit()

    async with session_factory() as session:
        search_repo = SqlAlchemySearchSessionRepository(session)
        loaded = await search_repo.get_by_id(session_entity.id)

    assert loaded is not None
    assert loaded.title == "Updated Search"
    assert loaded.search_offset == 100
    assert loaded.search_total == 120
    assert loaded.candidate_pool == []


@pytest.mark.asyncio
async def test_search_session_repository_save_raises_when_missing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    session_entity = build_search_session(employer_id=uuid4())

    async with session_factory() as session:
        repo = SqlAlchemySearchSessionRepository(session)
        with pytest.raises(SearchSessionNotFoundError):
            await repo.save(session_entity)


@pytest.mark.asyncio
async def test_search_session_repository_list_by_employer(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    employer = build_employer()
    first = build_search_session(employer_id=employer.id, title="First Search")
    second = build_search_session(employer_id=employer.id, title="Second Search")

    async with session_factory() as session:
        employer_repo = SqlAlchemyEmployerRepository(session)
        search_repo = SqlAlchemySearchSessionRepository(session)
        await employer_repo.add(employer)
        await search_repo.add(first)
        await search_repo.add(second)
        await session.commit()

    async with session_factory() as session:
        search_repo = SqlAlchemySearchSessionRepository(session)
        items = await search_repo.list_by_employer(employer.id, limit=10)

    assert len(items) == 2
    titles = {item.title for item in items}
    assert titles == {"First Search", "Second Search"}


@pytest.mark.asyncio
async def test_search_session_repository_list_by_employer_preserves_decisions_and_pool(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    employer = build_employer()
    first = build_search_session(employer_id=employer.id, title="First Search")
    second = build_search_session(employer_id=employer.id, title="Second Search")
    second_candidate_id = UUID("00000000-0000-0000-0000-000000000002")
    second.candidate_pool = [
        SearchSessionCandidate(
            id=uuid4(),
            session_id=second.id,
            rank_position=0,
            snapshot=SearchCandidateSnapshot(
                candidate_id=second_candidate_id,
                display_name="Bob",
                headline_role="Backend Engineer",
                experience_years=5.0,
                location="Berlin",
                skills=({"skill": "python", "level": 5},),
                salary_min=300000,
                salary_max=420000,
                currency="RUB",
                english_level="C1",
                about_me="Platform engineer",
                match_score=0.88,
                explanation={"rrf": 0.85},
            ),
            is_consumed=False,
        )
    ]
    first_decision = SearchDecision(
        candidate_id=UUID("00000000-0000-0000-0000-000000000010"),
        decision=DecisionType.LIKE,
        note="great fit",
    )
    second_decision = SearchDecision(
        candidate_id=UUID("00000000-0000-0000-0000-000000000011"),
        decision=DecisionType.SKIP,
        note="missing depth",
    )

    async with session_factory() as session:
        employer_repo = SqlAlchemyEmployerRepository(session)
        search_repo = SqlAlchemySearchSessionRepository(session)
        await employer_repo.add(employer)
        await search_repo.add(first)
        await search_repo.add(second)
        await search_repo.replace_pool(first.id, first.candidate_pool)
        await search_repo.replace_pool(second.id, second.candidate_pool)
        await search_repo.upsert_decision(first.id, first_decision)
        await search_repo.upsert_decision(second.id, second_decision)
        await session.commit()

    async with session_factory() as session:
        search_repo = SqlAlchemySearchSessionRepository(session)
        items = await search_repo.list_by_employer(employer.id, limit=10)

    by_title = {item.title: item for item in items}
    assert by_title["First Search"].candidate_pool
    assert by_title["Second Search"].candidate_pool
    assert first_decision.candidate_id in by_title["First Search"].decisions
    assert second_decision.candidate_id in by_title["Second Search"].decisions


@pytest.mark.asyncio
async def test_search_session_repository_upsert_decision_and_list_viewed(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    employer = build_employer()
    search_session = build_search_session(employer_id=employer.id)
    candidate_id = UUID("00000000-0000-0000-0000-000000000001")

    async with session_factory() as session:
        employer_repo = SqlAlchemyEmployerRepository(session)
        search_repo = SqlAlchemySearchSessionRepository(session)
        await employer_repo.add(employer)
        await search_repo.add(search_session)
        await session.commit()

    decision = SearchDecision(
        candidate_id=candidate_id,
        decision=DecisionType.LIKE,
        note="strong backend profile",
    )

    async with session_factory() as session:
        search_repo = SqlAlchemySearchSessionRepository(session)
        await search_repo.upsert_decision(search_session.id, decision)
        await session.commit()

    async with session_factory() as session:
        search_repo = SqlAlchemySearchSessionRepository(session)
        viewed_ids = await search_repo.list_viewed_candidate_ids(search_session.id)
        favorite_ids = await search_repo.list_favorite_candidate_ids(employer.id)
        loaded = await search_repo.get_by_id(search_session.id)

    assert viewed_ids == [candidate_id]
    assert favorite_ids == [candidate_id]
    assert loaded is not None
    assert candidate_id in loaded.decisions
    assert loaded.decisions[candidate_id].decision == DecisionType.LIKE


@pytest.mark.asyncio
async def test_search_session_repository_statistics(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    employer = build_employer()
    search_session = build_search_session(employer_id=employer.id)
    candidate_id = UUID("00000000-0000-0000-0000-000000000001")

    async with session_factory() as session:
        employer_repo = SqlAlchemyEmployerRepository(session)
        search_repo = SqlAlchemySearchSessionRepository(session)
        contact_repo = SqlAlchemyContactRequestRepository(session)

        await employer_repo.add(employer)
        await search_repo.add(search_session)

        like_decision = SearchDecision(
            candidate_id=candidate_id,
            decision=DecisionType.LIKE,
            note="great fit",
        )
        await search_repo.upsert_decision(search_session.id, like_decision)

        request = ContactRequest.create(
            id=uuid4(),
            employer_id=employer.id,
            candidate_id=candidate_id,
            status=ContactRequestStatus.GRANTED,
        )
        await contact_repo.add(request)
        await session.commit()

    async with session_factory() as session:
        search_repo = SqlAlchemySearchSessionRepository(session)
        employer_stats = await search_repo.get_employer_statistics(employer.id)
        candidate_stats = await search_repo.get_candidate_statistics(candidate_id)

    assert employer_stats == {
        "total_viewed": 1,
        "total_liked": 1,
        "total_contact_requests": 1,
        "total_contacts_granted": 1,
    }
    assert candidate_stats == {
        "total_views": 1,
        "total_likes": 1,
        "total_contact_requests": 1,
    }


@pytest.mark.asyncio
async def test_contact_request_repository_add_get_and_list_unlocked(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    employer = build_employer()
    candidate_id = uuid4()
    request = ContactRequest.create(
        id=uuid4(),
        employer_id=employer.id,
        candidate_id=candidate_id,
        status=ContactRequestStatus.PENDING,
    )

    async with session_factory() as session:
        employer_repo = SqlAlchemyEmployerRepository(session)
        contact_repo = SqlAlchemyContactRequestRepository(session)
        await employer_repo.add(employer)
        await contact_repo.add(request)
        await session.commit()

    async with session_factory() as session:
        contact_repo = SqlAlchemyContactRequestRepository(session)
        loaded_by_id = await contact_repo.get_by_id(request.id)
        loaded_by_pair = await contact_repo.get_by_employer_and_candidate(
            employer_id=employer.id,
            candidate_id=candidate_id,
        )

    assert loaded_by_id is not None
    assert loaded_by_pair is not None
    assert loaded_by_pair.granted is False

    request.approve()

    async with session_factory() as session:
        contact_repo = SqlAlchemyContactRequestRepository(session)
        await contact_repo.save(request)
        await session.commit()

    async with session_factory() as session:
        contact_repo = SqlAlchemyContactRequestRepository(session)
        unlocked_ids = await contact_repo.list_unlocked_candidate_ids(employer.id)

    assert unlocked_ids == [candidate_id]
