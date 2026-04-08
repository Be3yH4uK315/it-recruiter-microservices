from __future__ import annotations

import pytest

from app.domain.candidate.errors import InvalidSalaryRangeError
from app.domain.candidate.value_objects import SalaryRange


def test_salary_range_accepts_valid_values() -> None:
    salary = SalaryRange(
        min_amount=100000,
        max_amount=200000,
        currency="RUB",
    )

    assert salary.min_amount == 100000
    assert salary.max_amount == 200000
    assert salary.currency == "RUB"


def test_salary_range_accepts_none_bounds() -> None:
    salary = SalaryRange(
        min_amount=None,
        max_amount=None,
        currency="EUR",
    )

    assert salary.min_amount is None
    assert salary.max_amount is None
    assert salary.currency == "EUR"


def test_salary_range_rejects_negative_min() -> None:
    with pytest.raises(InvalidSalaryRangeError, match="salary_min must be >= 0"):
        SalaryRange(
            min_amount=-1,
            max_amount=100000,
            currency="RUB",
        )


def test_salary_range_rejects_negative_max() -> None:
    with pytest.raises(InvalidSalaryRangeError, match="salary_max must be >= 0"):
        SalaryRange(
            min_amount=100000,
            max_amount=-1,
            currency="RUB",
        )


def test_salary_range_rejects_max_less_than_min() -> None:
    with pytest.raises(InvalidSalaryRangeError, match="salary_max must be >= salary_min"):
        SalaryRange(
            min_amount=300000,
            max_amount=200000,
            currency="RUB",
        )


def test_salary_range_from_scalars_uses_default_currency() -> None:
    salary = SalaryRange.from_scalars(
        salary_min=150000,
        salary_max=250000,
        currency=None,
    )

    assert salary.currency == "RUB"
    assert salary.min_amount == 150000
    assert salary.max_amount == 250000
