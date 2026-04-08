from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.search.enums import WorkMode
from app.domain.search.errors import InvalidSearchFilterError
from app.domain.search.value_objects import SalaryRange, SearchFilters, SearchSkill


def test_search_skill_normalizes_skill_name() -> None:
    skill = SearchSkill(skill="  Python  ", level=4)
    assert skill.skill == "python"
    assert skill.level == 4


def test_search_skill_rejects_empty_name() -> None:
    with pytest.raises(InvalidSearchFilterError, match="skill must not be empty"):
        SearchSkill(skill="   ")


def test_search_skill_rejects_invalid_level() -> None:
    with pytest.raises(InvalidSearchFilterError, match="skill level must be in range 1..5"):
        SearchSkill(skill="python", level=6)


def test_salary_range_normalizes_currency() -> None:
    salary = SalaryRange(min_amount=100, max_amount=200, currency="usd")
    assert salary.currency == "USD"


def test_salary_range_rejects_negative_min() -> None:
    with pytest.raises(InvalidSearchFilterError, match="salary_min must be >= 0"):
        SalaryRange(min_amount=-1, max_amount=100, currency="RUB")


def test_salary_range_rejects_max_less_than_min() -> None:
    with pytest.raises(InvalidSearchFilterError, match="salary_max must be >= salary_min"):
        SalaryRange(min_amount=200, max_amount=100, currency="RUB")


def test_search_filters_normalize_role_location_and_english() -> None:
    filters = SearchFilters(
        role="  Python Developer  ",
        location="  Paris  ",
        english_level=" b2 ",
    )

    assert filters.role == "Python Developer"
    assert filters.location == "Paris"
    assert filters.english_level == "B2"


def test_search_filters_reject_short_role() -> None:
    with pytest.raises(InvalidSearchFilterError, match="role must contain at least 2 characters"):
        SearchFilters(role="A")


def test_search_filters_reject_invalid_experience_range() -> None:
    with pytest.raises(InvalidSearchFilterError, match="experience_max must be >= experience_min"):
        SearchFilters(
            role="Python Developer",
            experience_min=5,
            experience_max=2,
        )


def test_search_filters_deduplicate_skills() -> None:
    filters = SearchFilters(
        role="Python Developer",
        must_skills=(
            SearchSkill(skill="Python", level=5),
            SearchSkill(skill="python", level=4),
            SearchSkill(skill="FastAPI", level=4),
        ),
    )

    assert len(filters.must_skills) == 2
    assert filters.must_skills[0].skill == "python"
    assert filters.must_skills[1].skill == "fastapi"


def test_search_filters_to_primitives() -> None:
    exclude_id = uuid4()

    filters = SearchFilters(
        role="Python Developer",
        must_skills=(SearchSkill(skill="Python", level=5),),
        nice_skills=(SearchSkill(skill="Docker", level=3),),
        experience_min=2,
        experience_max=5,
        location="Berlin",
        work_modes=(WorkMode.REMOTE, WorkMode.HYBRID),
        salary_range=SalaryRange(min_amount=100000, max_amount=200000, currency="EUR"),
        english_level="B2",
        exclude_ids=(exclude_id,),
        about_me="Async microservices",
    )

    raw = filters.to_primitives()

    assert raw["role"] == "Python Developer"
    assert raw["must_skills"] == [{"skill": "python", "level": 5}]
    assert raw["nice_skills"] == [{"skill": "docker", "level": 3}]
    assert raw["experience_min"] == 2
    assert raw["experience_max"] == 5
    assert raw["location"] == "Berlin"
    assert raw["work_modes"] == ["remote", "hybrid"]
    assert raw["salary_min"] == 100000
    assert raw["salary_max"] == 200000
    assert raw["currency"] == "EUR"
    assert raw["english_level"] == "B2"
    assert raw["exclude_ids"] == [str(exclude_id)]
    assert raw["about_me"] == "Async microservices"
