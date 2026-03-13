from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.models.employer import (
    Decision,
    DecisionType,
    Employer,
)
from app.repositories.employer import EmployerRepository
from app.schemas.employer import (
    DecisionCreate,
    EmployerCreate,
    EmployerUpdate,
    SearchFilters,
    SearchSessionCreate,
)


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def repo(mock_session):
    return EmployerRepository(mock_session)


@pytest.mark.asyncio
async def test_get_by_telegram_id(repo, mock_session):
    mock_result = MagicMock()
    mock_scalars = MagicMock()

    emp = Employer(telegram_id=123)

    mock_scalars.first.return_value = emp
    mock_result.scalars.return_value = mock_scalars

    mock_session.execute.return_value = mock_result

    res = await repo.get_by_telegram_id(123)

    assert res == emp
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_employer(repo, mock_session):
    payload = EmployerCreate(telegram_id=123, company="Test", contacts={})

    res = await repo.create(payload)

    assert res.telegram_id == 123
    assert res.company == "Test"

    mock_session.add.assert_called_once_with(res)


@pytest.mark.asyncio
async def test_update_employer(repo, mock_session):
    mock_result = MagicMock()
    mock_scalars = MagicMock()

    emp = Employer(company="Updated")

    mock_scalars.first.return_value = emp
    mock_result.scalars.return_value = mock_scalars

    mock_session.execute.return_value = mock_result

    res = await repo.update(uuid4(), EmployerUpdate(company="Updated"))

    assert res == emp
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_session(repo, mock_session):
    filters = SearchFilters(role="Dev", must_skills=[{"skill": "python", "level": 3}])

    payload = SearchSessionCreate(title="Test", filters=filters)

    emp_id = uuid4()

    res = await repo.create_session(emp_id, payload)

    assert res.employer_id == emp_id
    assert res.title == "Test"

    mock_session.add.assert_called_once_with(res)


@pytest.mark.asyncio
async def test_get_viewed_candidate_ids(repo, mock_session):
    mock_result = MagicMock()
    mock_scalars = MagicMock()

    c_ids = [uuid4(), uuid4()]

    mock_scalars.all.return_value = c_ids
    mock_result.scalars.return_value = mock_scalars

    mock_session.execute.return_value = mock_result

    res = await repo.get_viewed_candidate_ids(uuid4())

    assert res == c_ids


@pytest.mark.asyncio
async def test_create_decision(repo, mock_session):
    mock_result = MagicMock()
    mock_scalars = MagicMock()

    dec = Decision(decision=DecisionType.LIKE)

    mock_scalars.one.return_value = dec
    mock_result.scalars.return_value = mock_scalars

    mock_session.execute.return_value = mock_result

    payload = DecisionCreate(candidate_id=uuid4(), decision=DecisionType.LIKE, note="Good")

    res = await repo.create_decision(uuid4(), payload)

    assert res == dec
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_contact_request_status(repo, mock_session):
    mock_result = MagicMock()
    mock_result.rowcount = 1

    mock_session.execute.return_value = mock_result

    res = await repo.update_contact_request_status(uuid4(), True)

    assert res is True


@pytest.mark.asyncio
async def test_get_statistics(repo, mock_session):
    # Тестируем агрегацию воронки
    mock_result = MagicMock()
    mock_result.scalar.side_effect = [100, 10, 5, 2]  # views, likes, reqs, granted

    mock_session.execute.return_value = mock_result

    res = await repo.get_statistics(uuid4())

    assert res["total_viewed"] == 100
    assert res["total_liked"] == 10
    assert res["total_contact_requests"] == 5
    assert res["total_contacts_granted"] == 2

    assert mock_session.execute.call_count == 4


@pytest.mark.asyncio
async def test_get_favorites_and_contacts(repo, mock_session):
    mock_result = MagicMock()
    mock_scalars = MagicMock()

    ids = [uuid4(), uuid4()]

    mock_scalars.all.return_value = ids
    mock_result.scalars.return_value = mock_scalars

    mock_session.execute.return_value = mock_result

    favs = await repo.get_favorites(uuid4())
    assert favs == ids

    conts = await repo.get_unlocked_contacts(uuid4())
    assert conts == ids
