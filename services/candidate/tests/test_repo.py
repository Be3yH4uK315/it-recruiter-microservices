from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from app.models.candidate import (
    Avatar,
    Candidate,
    CandidateSkill,
    Experience,
    Project,
    Resume,
    SkillKind,
    Status,
)
from app.repositories.candidate import CandidateRepository
from app.schemas.candidate import (
    CandidateCreate,
    CandidateSkillCreate,
    EducationItem,
    ExperienceCreate,
    ProjectCreate,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session):
    return CandidateRepository(mock_session)


@pytest.mark.asyncio
async def test_get_by_id(repo, mock_session):
    mock_result = MagicMock()
    mock_scalars = MagicMock()

    mock_result.scalars.return_value = mock_scalars

    cand = Candidate(id=uuid4(), display_name="Test")
    mock_scalars.first.return_value = cand

    mock_session.execute.return_value = mock_result

    res = await repo.get_by_id(cand.id)

    assert res == cand
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_telegram_id(repo, mock_session):
    mock_result = MagicMock()
    mock_scalars = MagicMock()

    mock_result.scalars.return_value = mock_scalars

    cand = Candidate(telegram_id=123)
    mock_scalars.first.return_value = cand

    mock_session.execute.return_value = mock_result

    res = await repo.get_by_telegram_id(123)

    assert res == cand


@pytest.mark.asyncio
async def test_get_paginated(repo, mock_session):
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 5

    mock_list_result = MagicMock()
    mock_scalars = MagicMock()

    cand = Candidate(id=uuid4())
    mock_scalars.all.return_value = [cand]

    mock_list_result.scalars.return_value = mock_scalars

    mock_session.execute.side_effect = [mock_count_result, mock_list_result]

    total, data = await repo.get_paginated(10, 0, search_query="test", skill_filter="python")

    assert total == 5
    assert len(data) == 1
    assert data[0] == cand

    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_create_candidate(repo, mock_session):
    payload = CandidateCreate(
        telegram_id=123,
        display_name="Test",
        headline_role="Dev",
        contacts={"email": "t@t.com"},
        skills=[CandidateSkillCreate(skill="python", kind="hard", level=5)],
        projects=[ProjectCreate(title="P1")],
        experiences=[ExperienceCreate(company="C1", position="D1", start_date="2020-01-01")],
        education=[EducationItem(level="BSc", institution="MSU", year=2020)],
    )

    res = await repo.create(payload)

    assert res.telegram_id == 123
    assert len(res.skills) == 1
    assert len(res.projects) == 1
    assert len(res.experiences) == 1
    assert len(res.education) == 1

    mock_session.add.assert_called_once_with(res)


@pytest.mark.asyncio
async def test_soft_delete(repo):
    cand = Candidate(status=Status.ACTIVE)

    await repo.soft_delete(cand)

    assert cand.status == Status.BLOCKED


@pytest.mark.asyncio
async def test_sync_skills(repo, mock_session):
    cand = Candidate(id=uuid4())

    old_skill = CandidateSkill(skill="java", kind=SkillKind.HARD, level=3)

    keep_skill = CandidateSkill(skill="python", kind=SkillKind.HARD, level=4)

    cand.skills = [old_skill, keep_skill]

    new_skills = [
        CandidateSkillCreate(skill="python", kind="hard", level=5),
        CandidateSkillCreate(skill="docker", kind="tool", level=4),
    ]

    await repo.sync_skills(cand, new_skills)

    assert keep_skill.level == 5

    mock_session.add.assert_called_once()
    mock_session.delete.assert_called_once_with(old_skill)


@pytest.mark.asyncio
async def test_replace_projects(repo, mock_session):
    cand = Candidate(id=uuid4())

    old_proj = Project(title="Old")
    cand.projects = [old_proj]

    new_projs = [ProjectCreate(title="New")]

    await repo.replace_projects(cand, new_projs)

    mock_session.delete.assert_called_once_with(old_proj)

    mock_session.add_all.assert_called_once()

    args = mock_session.add_all.call_args[0][0]

    assert len(args) == 1
    assert args[0].title == "New"


@pytest.mark.asyncio
async def test_replace_avatar(repo, mock_session):
    cand = Candidate(id=uuid4())

    old_avatar = Avatar(file_id=uuid4())
    cand.avatars = [old_avatar]

    new_file_id = uuid4()

    old_file_id = await repo.replace_avatar(cand, new_file_id)

    assert old_file_id == old_avatar.file_id

    mock_session.delete.assert_called_once_with(old_avatar)
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_delete_avatar(repo, mock_session):
    cand = Candidate(id=uuid4())

    old_avatar = Avatar(file_id=uuid4())
    cand.avatars = [old_avatar]

    deleted_id = await repo.delete_avatar(cand)

    assert deleted_id == old_avatar.file_id

    mock_session.delete.assert_called_once_with(old_avatar)


@pytest.mark.asyncio
async def test_replace_resume(repo, mock_session):
    cand = Candidate(id=uuid4())

    old_resume = Resume(file_id=uuid4())
    cand.resumes = [old_resume]

    new_file_id = uuid4()

    old_file_id = await repo.replace_resume(cand, new_file_id)

    assert old_file_id == old_resume.file_id

    mock_session.delete.assert_called_once_with(old_resume)
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_replace_experiences(repo, mock_session):
    cand = Candidate(id=uuid4())

    old_exp = Experience(company="Old")
    cand.experiences = [old_exp]

    new_exp = [
        ExperienceCreate(
            company="New",
            position="Dev",
            start_date="2020-01-01",
        )
    ]

    await repo.replace_experiences(cand, new_exp)

    mock_session.delete.assert_called_once_with(old_exp)
    mock_session.add_all.assert_called_once()
