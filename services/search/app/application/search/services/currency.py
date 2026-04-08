from __future__ import annotations

from app.domain.search.errors import InvalidSearchFilterError

DEFAULT_CURRENCY = "RUB"

CURRENCY_RATES_TO_RUB: dict[str, float] = {
    "RUB": 1.0,
    "USD": 95.0,
    "EUR": 105.0,
}


def normalize_currency_code(currency: str | None) -> str:
    normalized = (currency or DEFAULT_CURRENCY).strip().upper()
    return normalized or DEFAULT_CURRENCY


def get_currency_rate_to_rub(currency: str | None) -> float:
    code = normalize_currency_code(currency)
    rate = CURRENCY_RATES_TO_RUB.get(code)
    if rate is None:
        raise InvalidSearchFilterError(f"unsupported currency: {code}")
    return rate


def normalize_to_rub(amount: float | int | None, currency: str | None) -> float | None:
    if amount is None:
        return None

    return float(amount) * get_currency_rate_to_rub(currency)
