from __future__ import annotations

from types import SimpleNamespace

from app.application.search.services.scoring import (
    calculate_multiplicative_score,
    sigmoid,
)
from app.domain.search.enums import WorkMode
from app.domain.search.value_objects import SalaryRange, SearchFilters, SearchSkill


def make_settings() -> SimpleNamespace:
    return SimpleNamespace(
        factor_no_skills=0.85,
        factor_exp_mismatch=0.90,
        factor_location_match=1.10,
    )


def test_sigmoid_returns_value_between_zero_and_one() -> None:
    value = sigmoid(0.5)
    assert 0.0 < value < 1.0


def test_scoring_returns_positive_score_and_explanation() -> None:
    filters = SearchFilters(
        role="Python Developer",
        must_skills=(SearchSkill(skill="Python", level=5),),
        nice_skills=(SearchSkill(skill="FastAPI", level=4),),
        experience_min=2,
        experience_max=6,
        location="Paris",
        work_modes=(WorkMode.REMOTE,),
        salary_range=SalaryRange(min_amount=100000, max_amount=250000, currency="RUB"),
        english_level="B2",
    )
    candidate = {
        "skills": [{"skill": "python"}, {"skill": "fastapi"}],
        "experience_years": 4.0,
        "location": "Paris",
        "work_modes": ["remote"],
        "salary_min_rub": 180000.0,
        "english_level": "B2",
    }

    score, explanation = calculate_multiplicative_score(
        candidate=candidate,
        filters=filters,
        raw_ranker_score=1.25,
        settings=make_settings(),
    )

    assert score > 0
    assert "ml_score" in explanation
    assert "skill_factor" in explanation
    assert "experience_factor" in explanation
    assert "location_factor" in explanation
    assert "salary_factor" in explanation
    assert "english_factor" in explanation
    assert "final_score" in explanation


def test_scoring_penalizes_experience_mismatch() -> None:
    filters = SearchFilters(
        role="Python Developer",
        experience_min=5,
    )
    candidate = {
        "skills": [],
        "experience_years": 2.0,
    }

    score, explanation = calculate_multiplicative_score(
        candidate=candidate,
        filters=filters,
        raw_ranker_score=1.0,
        settings=make_settings(),
    )

    assert score > 0
    assert explanation["experience_factor"] < 1.0


def test_scoring_applies_location_bonus_for_remote_match() -> None:
    filters = SearchFilters(
        role="Python Developer",
        location="Berlin",
        work_modes=(WorkMode.REMOTE,),
    )
    candidate = {
        "skills": [],
        "experience_years": 3.0,
        "location": "Warsaw",
        "work_modes": ["remote"],
    }

    score, explanation = calculate_multiplicative_score(
        candidate=candidate,
        filters=filters,
        raw_ranker_score=0.7,
        settings=make_settings(),
    )

    assert score > 0
    assert explanation["location_factor"] == 1.0


def test_scoring_penalizes_onsite_without_location_match() -> None:
    filters = SearchFilters(
        role="Python Developer",
        location="Berlin",
        work_modes=(WorkMode.ONSITE,),
    )
    candidate = {
        "skills": [],
        "experience_years": 3.0,
        "location": "Warsaw",
        "work_modes": ["onsite"],
    }

    score, explanation = calculate_multiplicative_score(
        candidate=candidate,
        filters=filters,
        raw_ranker_score=0.7,
        settings=make_settings(),
    )

    assert score > 0
    assert explanation["location_factor"] == 0.7


def test_scoring_slightly_penalizes_hybrid_without_location_match() -> None:
    filters = SearchFilters(
        role="Python Developer",
        location="Berlin",
        work_modes=(WorkMode.HYBRID,),
    )
    candidate = {
        "skills": [],
        "experience_years": 3.0,
        "location": "Warsaw",
        "work_modes": ["hybrid"],
    }

    score, explanation = calculate_multiplicative_score(
        candidate=candidate,
        filters=filters,
        raw_ranker_score=0.7,
        settings=make_settings(),
    )

    assert score > 0
    assert explanation["location_factor"] == 0.95


def test_scoring_penalizes_salary_mismatch() -> None:
    filters = SearchFilters(
        role="Python Developer",
        salary_range=SalaryRange(min_amount=100000, max_amount=150000, currency="RUB"),
    )
    candidate = {
        "skills": [],
        "experience_years": 3.0,
        "salary_min_rub": 200000.0,
    }

    score, explanation = calculate_multiplicative_score(
        candidate=candidate,
        filters=filters,
        raw_ranker_score=1.0,
        settings=make_settings(),
    )

    assert score > 0
    assert explanation["salary_factor"] < 1.0


def test_scoring_penalizes_english_mismatch() -> None:
    filters = SearchFilters(
        role="Python Developer",
        english_level="B2",
    )
    candidate = {
        "skills": [],
        "experience_years": 3.0,
        "english_level": "A2",
    }

    score, explanation = calculate_multiplicative_score(
        candidate=candidate,
        filters=filters,
        raw_ranker_score=1.0,
        settings=make_settings(),
    )

    assert score > 0
    assert explanation["english_factor"] < 1.0


def test_scoring_uses_skill_coverage_when_skills_present() -> None:
    filters = SearchFilters(
        role="Python Developer",
        must_skills=(SearchSkill(skill="Python", level=5),),
        nice_skills=(SearchSkill(skill="Docker", level=3),),
    )
    candidate = {
        "skills": [{"skill": "python"}],
        "experience_years": 3.0,
    }

    score, explanation = calculate_multiplicative_score(
        candidate=candidate,
        filters=filters,
        raw_ranker_score=1.0,
        settings=make_settings(),
    )

    assert score > 0
    assert explanation["skill_factor"] >= 0.85
