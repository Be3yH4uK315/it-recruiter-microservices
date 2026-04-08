from __future__ import annotations

import pytest

from app.domain.employer.enums import WorkMode
from app.domain.employer.errors import InvalidSearchFilterError
from app.domain.employer.value_objects import SalaryRange, SearchFilters, SearchSkill


def test_salary_range_valid() -> None:
    salary = SalaryRange(min_amount=100000, max_amount=200000, currency="rub")
    assert salary.min_amount == 100000
    assert salary.max_amount == 200000
    assert salary.currency == "RUB"


def test_salary_range_invalid_when_max_less_than_min() -> None:
    with pytest.raises(InvalidSearchFilterError):
        SalaryRange(min_amount=200000, max_amount=100000, currency="RUB")


def test_search_skill_normalizes_name() -> None:
    skill = SearchSkill(skill="  Python  ", level=5)
    assert skill.skill == "python"
    assert skill.level == 5


def test_search_filters_deduplicates_skills() -> None:
    filters = SearchFilters(
        role="Python Developer",
        must_skills=(
            SearchSkill(skill="python", level=5),
            SearchSkill(skill="Python", level=4),
        ),
        work_modes=(WorkMode.REMOTE,),
    )
    assert len(filters.must_skills) == 1
    assert filters.must_skills[0].skill == "python"
