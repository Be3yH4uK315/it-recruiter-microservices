import pytest
from datetime import date
from uuid import uuid4
from app.schemas.candidate import Candidate, Experience

def create_experience(start, end, company="A"):
    return Experience(
        id=uuid4(),
        candidate_id=uuid4(),
        company=company,
        position="Dev",
        start_date=start,
        end_date=end,
        responsibilities="Code"
    )

def create_dummy_candidate(experiences=[]):
    return Candidate(
        id=uuid4(),
        telegram_id=123,
        display_name="Tester",
        headline_role="QA",
        location="Earth",
        work_modes=["remote"],
        contacts={},
        education=[],
        skills=[],
        projects=[],
        avatars=[],
        resumes=[],
        status="active",
        contacts_visibility="public",
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
        experiences=experiences
    )

def test_experience_years_calculation_simple():
    """Тест: 1 год опыта (без наложений)."""
    exp = create_experience(date(2020, 1, 1), date(2021, 1, 1))
    cand = create_dummy_candidate([exp])
    assert cand.experience_years == 1.0

def test_experience_years_overlap():
    """Тест: Пересекающиеся интервалы (параллельная работа)."""
    exp1 = create_experience(date(2020, 1, 1), date(2020, 12, 31), company="A")
    exp2 = create_experience(date(2020, 6, 1), date(2021, 6, 30), company="B")
    cand = create_dummy_candidate([exp1, exp2])
    
    assert cand.experience_years == 1.5

def test_experience_years_current_job():
    """Тест: Работа по настоящее время (None в end_date)."""
    today = date.today()
    start = date(today.year - 2, today.month, today.day)
    exp = create_experience(start, None, company="Current")
    cand = create_dummy_candidate([exp])
    
    assert 1.9 <= cand.experience_years <= 2.1

def test_experience_years_empty():
    """Тест: Нет опыта."""
    cand = create_dummy_candidate([])
    assert cand.experience_years == 0.0
