from __future__ import annotations

import pytest

from app.application.search.services.currency import (
    DEFAULT_CURRENCY,
    normalize_currency_code,
    normalize_to_rub,
)
from app.domain.search.errors import InvalidSearchFilterError


def test_normalize_currency_code_uses_default_for_none() -> None:
    assert normalize_currency_code(None) == DEFAULT_CURRENCY


def test_normalize_currency_code_strips_and_uppercases() -> None:
    assert normalize_currency_code("usd") == "USD"


def test_normalize_to_rub_returns_none_for_none_amount() -> None:
    assert normalize_to_rub(None, "RUB") is None


@pytest.mark.parametrize(
    ("amount", "currency", "expected"),
    [
        (100, "RUB", 100.0),
        (10, "USD", 950.0),
        (10, "EUR", 1050.0),
    ],
)
def test_normalize_to_rub_known_currency(
    amount: int,
    currency: str,
    expected: float,
) -> None:
    assert normalize_to_rub(amount, currency) == expected


def test_normalize_to_rub_uses_default_currency_when_none() -> None:
    assert normalize_to_rub(100, None) == 100.0


def test_normalize_to_rub_raises_for_unknown_currency() -> None:
    with pytest.raises(InvalidSearchFilterError, match="unsupported currency"):
        normalize_to_rub(100, "ABC")
